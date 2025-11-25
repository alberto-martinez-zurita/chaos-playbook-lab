#!/usr/bin/env python3
"""
Extrae contenido recursivo de un proyecto Python.
Respeta .gitignore y filtra archivos relevantes.
"""

import os
import pathlib
from pathlib import Path

def parse_gitignore(root_path):
    """Parse .gitignore patterns"""
    gitignore_path = root_path / '.gitignore'
    patterns = []
    
    if gitignore_path.exists():
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if line and not line.startswith('#'):
                    patterns.append(line)
    
    # Add default patterns
    patterns.extend([
        '__pycache__', '*.pyc', '*.pyo', '*.pyd',
        '.git', '.venv', 'venv', 'env',
        '.pytest_cache', '.mypy_cache', '.tox',
        '*.egg-info', 'dist', 'build',
        '.DS_Store', 'Thumbs.db'
    ])
    
    return patterns

def should_ignore(path, patterns, root):
    """Check if path should be ignored"""
    rel_path = path.relative_to(root)
    path_str = str(rel_path)
    
    for pattern in patterns:
        # Simple pattern matching
        if pattern in path_str or path.name == pattern:
            return True
        if pattern.startswith('*') and path_str.endswith(pattern[1:]):
            return True
        if pattern.endswith('/') and pattern[:-1] in path_str:
            return True
    
    return False

def extract_project_content(root_path, output_file='project_content.txt'):
    """Extract all relevant Python project files"""
    root = Path(root_path).resolve()
    patterns = parse_gitignore(root)
    
    # Relevant file extensions
    relevant_extensions = {
        '.py',         # Python source
        '.md',         # Markdown docs
        '.txt',        # Text files
        '.yaml', '.yml',  # Config
        '.toml',       # pyproject.toml
        '.json',       # JSON config
        '.ini', '.cfg'  # Config files
    }
    
    files_content = []
    file_list = []
    
    # Walk through directory
    for path in sorted(root.rglob('*')):
        # Skip directories
        if path.is_dir():
            continue
            
        # Skip ignored patterns
        if should_ignore(path, patterns, root):
            continue
        
        # Only relevant extensions
        if path.suffix not in relevant_extensions:
            continue
        
        rel_path = path.relative_to(root)
        file_list.append(str(rel_path))
        
        # Read file content
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            files_content.append(f"\n{'=' * 80}\n")
            files_content.append(f"FILE: {rel_path}\n")
            files_content.append(f"{'=' * 80}\n\n")
            files_content.append(content)
            files_content.append("\n\n")
        
        except Exception as e:
            print(f"⚠️  Could not read {rel_path}: {e}")
    
    # Write output
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"PROJECT CONTENT EXTRACTION\n")
        f.write(f"Root: {root}\n")
        f.write(f"Total files: {len(file_list)}\n\n")
        f.write("=" * 80 + "\n")
        f.write("FILE LIST:\n")
        f.write("=" * 80 + "\n\n")
        for file_path in file_list:
            f.write(f"  - {file_path}\n")
        f.write("\n" + "=" * 80 + "\n\n")
        f.writelines(files_content)
    
    print(f"✅ Extracted {len(file_list)} files to {output_file}")
    print(f"\n📁 Files included:")
    for fp in file_list[:10]:
        print(f"  - {fp}")
    if len(file_list) > 10:
        print(f"  ... and {len(file_list) - 10} more")

# USO
if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        project_path = sys.argv[1]
    else:
        project_path = '.'  # Current directory
    
    output = 'project_content.txt'
    if len(sys.argv) > 2:
        output = sys.argv[2]
    
    extract_project_content(project_path, output)
