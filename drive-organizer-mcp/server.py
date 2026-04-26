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
def push_to_drive(file_path: str, category: str, descriptive_name: str, execute: bool = False, always_allow: bool = False, target_account: str = None) -> str:
    """
    Move the file to the Google Drive folder for the given category with the descriptive name.
    The descriptive_name should usually be in the format 'YYYY-MM-DD_name.ext'.
    
    HOW TO USE THIS TOOL AS AN AI AGENT:
    1. By default (execute=False), this tool will return the planned destination. You MUST show this to the user and ask for permission before moving the file.
    2. If the user approves, call this tool again with execute=True.
    3. If the user says "always allow", call this tool with execute=True and always_allow=True. This will save their preference.
    4. If there are multiple accounts, the user can specify target_account or the tool will prompt for it.
    """
    if not os.path.exists(file_path):
        return f"Error: File not found: {file_path}"
        
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

if __name__ == "__main__":
    # Start the server
    mcp.run()
