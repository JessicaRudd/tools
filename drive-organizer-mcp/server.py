import os
import shutil
from mcp.server.fastmcp import FastMCP
import exifread
from pdfminer.high_level import extract_text as extract_pdf_text
import docx

# Initialize FastMCP server
mcp = FastMCP("drive_organizer")

@mcp.tool()
def extract_file_metadata(file_path: str) -> str:
    """
    Extract text and metadata from a file (PDF, DOCX, or Image).
    Returns the raw text and EXIF dates if available, to be used by the Agent to determine
    the correct category and a descriptive filename.
    """
    if not os.path.exists(file_path):
        return f"Error: File not found: {file_path}"
        
    ext = os.path.splitext(file_path)[1].lower()
    
    metadata = f"File Path: {file_path}\n"
    
    try:
        if ext in ['.pdf']:
            text = extract_pdf_text(file_path)
            metadata += f"PDF Text Preview (first 1000 chars):\n{text[:1000]}"
        elif ext in ['.docx']:
            doc = docx.Document(file_path)
            text = '\n'.join([para.text for para in doc.paragraphs])
            metadata += f"Word Document Text Preview (first 1000 chars):\n{text[:1000]}"
        elif ext in ['.jpg', '.jpeg', '.png', '.tiff']:
            with open(file_path, 'rb') as f:
                tags = exifread.process_file(f, details=False)
                date_taken = tags.get('EXIF DateTimeOriginal') or tags.get('Image DateTime')
                if date_taken:
                    metadata += f"EXIF Date Taken: {date_taken}\n"
                else:
                    metadata += "No EXIF date found in image.\n"
        else:
            with open(file_path, 'r', errors='ignore') as f:
                text = f.read(1000)
                metadata += f"Raw Text Preview (first 1000 chars):\n{text}"
    except Exception as e:
        metadata += f"Error extracting metadata: {e}"
        
    return metadata

import json

CONFIG_FILE = os.path.expanduser("~/.drive_organizer_config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def find_category_folder(drive_root: str, target_category: str) -> str:
    target_lower = target_category.lower()
    for root, dirs, files in os.walk(drive_root):
        # Skip hidden directories to speed up search
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for d in dirs:
            if d.lower() == target_lower:
                return os.path.join(root, d)
    return None

def get_available_drive_roots():
    home = os.path.expanduser("~")
    roots = {}
    try:
        for d in os.listdir(home):
            if d.endswith(" - Google Drive"):
                account = d.replace(" - Google Drive", "")
                drive_root = os.path.join(home, d, "My Drive")
                if os.path.exists(drive_root):
                    roots[account] = drive_root
    except Exception:
        pass
        
    # Fallback if old format exists
    old_root = os.path.join(home, "Google Drive", "My Drive")
    if os.path.exists(old_root) and not roots:
        roots["default"] = old_root
        
    return roots

@mcp.tool()
def get_drive_structure(target_account: str = None, max_depth: int = 2) -> str:
    """
    Get the directory structure of Google Drive up to a certain depth to suggest folder locations.
    """
    drive_roots = get_available_drive_roots()
    if not drive_roots:
        return "Error: No Google Drive folders found in your home directory."
        
    config = load_config()
    
    if not target_account:
        target_account = config.get("default_account")
        
    if not target_account:
        if len(drive_roots) == 1:
            target_account = list(drive_roots.keys())[0]
        else:
            accounts = list(drive_roots.keys())
            return (f"Error: Multiple Google Drive accounts found: {accounts}. "
                    f"Agent: Please ask the user which account they want to use, and call this tool again with target_account set to the chosen account.")
                    
    if target_account not in drive_roots:
        return f"Error: The account '{target_account}' is not available."
        
    drive_root = drive_roots[target_account]
    
    # Traverse directories
    structure = []
    
    for root, dirs, files in os.walk(drive_root):
        # Calculate current depth
        rel_path = os.path.relpath(root, drive_root)
        if rel_path == '.':
            depth = 0
        else:
            depth = rel_path.count(os.sep) + 1
            
        if depth >= max_depth:
            dirs[:] = [] # Stop traversing deeper
            continue
            
        # Skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for d in dirs:
            dir_path = os.path.relpath(os.path.join(root, d), drive_root)
            structure.append(dir_path)
            
    if not structure:
        return "No folders found."
        
    return "Existing folders (up to depth {}):\n".format(max_depth) + "\n".join(sorted(structure))

@mcp.tool()
def push_to_drive(file_path: str, category: str = "", descriptive_name: str = "", execute: bool = False, always_allow: bool = False, target_account: str = None, target_path: str = None) -> str:
    """
    Move the file to the Google Drive folder.
    Provide EITHER 'category' (to auto-find a matching loose folder) OR 'target_path' (an explicit nested path like 'Learning/Spanish').
    The descriptive_name should usually be in the format 'YYYY-MM-DD_name.ext'.
    
    HOW TO USE THIS TOOL AS AN AI AGENT:
    1. By default (execute=False), this tool will return the planned destination. You MUST show this to the user and ask for permission before moving the file.
    2. If the user approves, call this tool again with execute=True.
    3. If the user says "always allow", call this tool with execute=True and always_allow=True. This will save their preference.
    4. If there are multiple accounts, the user can specify target_account or the tool will prompt for it.
    """
    if not os.path.exists(file_path):
        return f"Error: File not found: {file_path}"
        
    if not category and not target_path:
        return "Error: You must provide either 'category' or 'target_path'."
        
    drive_roots = get_available_drive_roots()
    if not drive_roots:
        return "Error: No Google Drive folders found in your home directory."
        
    config = load_config()
    
    if not target_account:
        target_account = config.get("default_account")
        
    if not target_account:
        if len(drive_roots) == 1:
            target_account = list(drive_roots.keys())[0]
        else:
            accounts = list(drive_roots.keys())
            return (f"Error: Multiple Google Drive accounts found: {accounts}. "
                    f"Agent: Please ask the user which account they want to use, and call this tool again with target_account set to the chosen account.")
                    
    if target_account not in drive_roots:
        return f"Error: The account '{target_account}' is not available. Available accounts are: {list(drive_roots.keys())}."
        
    drive_root = drive_roots[target_account]
        
    if target_path:
        category_path = os.path.join(drive_root, target_path)
    else:
        found_path = find_category_folder(drive_root, category)
        if found_path:
            category_path = found_path
        else:
            category_path = os.path.join(drive_root, category)
        
    destination_path = os.path.join(category_path, descriptive_name)
    
    if always_allow:
        config['always_allow'] = True
        config['default_account'] = target_account
        save_config(config)
        
    is_always_allow = config.get('always_allow', False)
    
    if not execute and not is_always_allow:
        return (f"PLAN: File will be moved to {destination_path} (Account: {target_account}). "
                f"Agent: Please ask the user for permission. "
                f"If they approve, call this tool again with execute=True. "
                f"If they say 'always allow', call with execute=True and always_allow=True.")
                
    os.makedirs(category_path, exist_ok=True)
    
    try:
        shutil.move(file_path, destination_path)
        msg = f"Successfully moved file to {destination_path}"
        if always_allow:
            msg += " ('Always allow' preference saved for future files)."
        return msg
    except Exception as e:
        return f"Error moving file: {e}"

@mcp.tool()
def create_drive_folder(target_path: str, target_account: str = None, execute: bool = False) -> str:
    """
    Create a new folder in Google Drive at the specified target_path (e.g., 'Learning/Spanish').
    
    HOW TO USE THIS TOOL AS AN AI AGENT:
    1. By default (execute=False), this tool will return the planned folder creation path. You MUST show this to the user and ask for permission before creating it.
    2. If the user approves, call this tool again with execute=True.
    """
    if not target_path:
        return "Error: You must provide 'target_path'."
        
    drive_roots = get_available_drive_roots()
    if not drive_roots:
        return "Error: No Google Drive folders found in your home directory."
        
    config = load_config()
    
    if not target_account:
        target_account = config.get("default_account")
        
    if not target_account:
        if len(drive_roots) == 1:
            target_account = list(drive_roots.keys())[0]
        else:
            accounts = list(drive_roots.keys())
            return (f"Error: Multiple Google Drive accounts found: {accounts}. "
                    f"Agent: Please ask the user which account they want to use, and call this tool again with target_account set to the chosen account.")
                    
    if target_account not in drive_roots:
        return f"Error: The account '{target_account}' is not available. Available accounts are: {list(drive_roots.keys())}."
        
    drive_root = drive_roots[target_account]
    category_path = os.path.join(drive_root, target_path)
    
    if not execute:
        return (f"PLAN: Folder will be created at {category_path} (Account: {target_account}). "
                f"Agent: Please ask the user for permission. "
                f"If they approve, call this tool again with execute=True.")
                
    try:
        os.makedirs(category_path, exist_ok=True)
        return f"Successfully created folder at {category_path}"
    except Exception as e:
        return f"Error creating folder: {e}"

@mcp.tool()
def move_across_drives(source_account: str, source_path: str, target_account: str, target_path: str, execute: bool = False) -> str:
    """
    Move a file or folder from one Google Drive account to another.
    
    HOW TO USE THIS TOOL AS AN AI AGENT:
    1. By default (execute=False), this tool will return the planned cross-drive move. You MUST show this to the user and ask for permission.
    2. If the user approves, call this tool again with execute=True.
    """
    drive_roots = get_available_drive_roots()
    if source_account not in drive_roots:
        return f"Error: Source account '{source_account}' is not available. Available: {list(drive_roots.keys())}"
    if target_account not in drive_roots:
        return f"Error: Target account '{target_account}' is not available. Available: {list(drive_roots.keys())}"
        
    src_full_path = os.path.join(drive_roots[source_account], source_path)
    dest_full_path = os.path.join(drive_roots[target_account], target_path)
    
    if not os.path.exists(src_full_path):
        return f"Error: Source path does not exist: {src_full_path}"
        
    if not execute:
        return (f"PLAN: Cross-Drive Move\n"
                f"Source: {src_full_path} (Account: {source_account})\n"
                f"Target: {dest_full_path} (Account: {target_account})\n"
                f"Agent: Please ask the user for permission. If they approve, call with execute=True.")
                
    try:
        # Create parent directories for target if they don't exist
        os.makedirs(os.path.dirname(dest_full_path), exist_ok=True)
        shutil.move(src_full_path, dest_full_path)
        return f"Successfully moved '{source_path}' to '{target_account}' at '{target_path}'"
    except Exception as e:
        return f"Error moving across drives: {e}"

@mcp.tool()
def migration_assessment(source_account: str, target_account: str, path: str = "", max_depth: int = 1) -> str:
    """
    Scan two Google Drives to assess migration from source_account to target_account.
    Returns a structured report of items to Migrate, Merge, or potentially Duplicate/Delete.
    """
    drive_roots = get_available_drive_roots()
    if source_account not in drive_roots:
        return f"Error: Source account '{source_account}' is not available. Available: {list(drive_roots.keys())}"
    if target_account not in drive_roots:
        return f"Error: Target account '{target_account}' is not available. Available: {list(drive_roots.keys())}"
        
    src_root = os.path.join(drive_roots[source_account], path)
    tgt_root = os.path.join(drive_roots[target_account], path)
    
    if not os.path.exists(src_root):
        return f"Error: Source path does not exist: {src_root}"
        
    report = {
        "migrate": [], # Exists in source, missing in target
        "merge": [],   # Folder exists in both
        "duplicate": [] # File exists in both
    }
    
    for root, dirs, files in os.walk(src_root):
        rel_path = os.path.relpath(root, src_root)
        if rel_path == '.':
            depth = 0
            rel_path = ""
        else:
            depth = rel_path.count(os.sep) + 1
            
        if depth >= max_depth:
            dirs[:] = []
            continue
            
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for d in dirs:
            dir_rel_path = os.path.join(rel_path, d) if rel_path else d
            tgt_dir = os.path.join(tgt_root, dir_rel_path)
            if os.path.exists(tgt_dir):
                report["merge"].append(dir_rel_path)
            else:
                report["migrate"].append(dir_rel_path)
                
        for f in files:
            if f.startswith('.'): continue
            file_rel_path = os.path.join(rel_path, f) if rel_path else f
            tgt_file = os.path.join(tgt_root, file_rel_path)
            if os.path.exists(tgt_file):
                report["duplicate"].append(file_rel_path)
            else:
                report["migrate"].append(file_rel_path)
                
    output = f"Migration Assessment: {source_account} -> {target_account} (Path: '{path}', Max Depth: {max_depth})\n"
    output += "=" * 60 + "\n"
    
    output += "\n[TO MIGRATE] (Exists in source, missing in target):\n"
    if report["migrate"]:
        for item in sorted(report["migrate"]):
            output += f"  - {item}\n"
    else:
        output += "  (None)\n"
        
    output += "\n[TO MERGE] (Folders existing in both):\n"
    if report["merge"]:
        for item in sorted(report["merge"]):
            output += f"  - {item}\n"
    else:
        output += "  (None)\n"
        
    output += "\n[POTENTIAL DUPLICATES] (Files existing in both):\n"
    if report["duplicate"]:
        for item in sorted(report["duplicate"]):
            output += f"  - {item}\n"
    else:
        output += "  (None)\n"
        
    return output

if __name__ == "__main__":
    # Start the server
    mcp.run()
