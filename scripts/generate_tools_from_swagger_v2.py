"""
generate_tools_from_swagger.py - Auto-generate Python tool wrappers from OpenAPI Swagger

UPDATED: Support for local file input or URL

USAGE:
    # From URL
    python scripts/generate_tools_from_swagger.py \
        --swagger-url https://petstore3.swagger.io/api/v3/openapi.json \
        --output src/chaos_playbook_engine/tools/petstore_tools.py
    
    # From local file
    python scripts/generate_tools_from_swagger.py \
        --swagger-file apis/petstore3_openapi.json \
        --output src/chaos_playbook_engine/tools/petstore_tools.py

PURPOSE:
    Read Swagger/OpenAPI specification and generate Python functions that wrap
    each API endpoint as an ADK-compatible tool.

AUTHOR: Auto-generated script for chaos-playbook-engine Phase 6
DATE: 2025-11-26 (Updated)
"""

import argparse
import json
import requests
from typing import Dict, List, Any
from pathlib import Path


def fetch_swagger_spec(swagger_url: str = None, swagger_file: str = None) -> Dict[str, Any]:
    """
    Load Swagger/OpenAPI specification from URL or local file.
    
    Args:
        swagger_url: URL to swagger.json or OpenAPI spec (optional)
        swagger_file: Path to local swagger/openapi JSON file (optional)
    
    Returns:
        dict: Parsed Swagger specification
    
    Raises:
        ValueError: If neither URL nor file provided
        FileNotFoundError: If local file doesn't exist
        requests.RequestException: If URL download fails
        json.JSONDecodeError: If JSON parsing fails
    """
    if swagger_file:
        # Load from local file
        file_path = Path(swagger_file)
        if not file_path.exists():
            raise FileNotFoundError(f"Swagger file not found: {swagger_file}")
        
        print(f"📂 Reading Swagger spec from: {swagger_file}")
        with open(file_path, 'r', encoding='utf-8') as f:
            spec = json.load(f)
        
        print(f"✅ Successfully loaded Swagger spec")
        print(f"   Title: {spec.get('info', {}).get('title', 'Unknown')}")
        print(f"   Version: {spec.get('info', {}).get('version', 'Unknown')}")
        return spec
    
    elif swagger_url:
        # Download from URL
        print(f"📥 Downloading Swagger spec from: {swagger_url}")
        try:
            response = requests.get(swagger_url, timeout=10)
            response.raise_for_status()
            spec = response.json()
            
            print(f"✅ Successfully downloaded Swagger spec")
            print(f"   Title: {spec.get('info', {}).get('title', 'Unknown')}")
            print(f"   Version: {spec.get('info', {}).get('version', 'Unknown')}")
            return spec
        
        except requests.RequestException as e:
            print(f"❌ Error downloading Swagger spec: {e}")
            raise
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing Swagger JSON: {e}")
            raise
    
    else:
        raise ValueError("Must provide either --swagger-url or --swagger-file")


def generate_param_doc(parameters: List[Dict[str, Any]]) -> str:
    """
    Generate docstring for parameters section.
    
    Args:
        parameters: List of parameter definitions from Swagger
    
    Returns:
        str: Formatted parameter documentation
    """
    if not parameters:
        return "        None"
    
    param_docs = []
    for param in parameters:
        name = param.get('name', 'unknown')
        param_type = param.get('type', param.get('schema', {}).get('type', 'any'))
        description = param.get('description', 'No description')
        required = param.get('required', False)
        location = param.get('in', 'unknown')
        
        required_str = "required" if required else "optional"
        param_docs.append(f"        - {name} ({location}, {required_str}): {description}")
    
    return "\n".join(param_docs)


def generate_tool_function(operation_id: str, path: str, method: str, spec: Dict[str, Any]) -> str:
    """
    Generate Python function code for a single API endpoint.
    
    Args:
        operation_id: Unique operation ID from Swagger
        path: API path (e.g., /pet/{petId})
        method: HTTP method (get, post, put, delete)
        spec: Operation specification from Swagger
    
    Returns:
        str: Python function code
    """
    summary = spec.get('summary', 'No summary available')
    description = spec.get('description', '')
    parameters = spec.get('parameters', [])
    
    # Generate parameter documentation
    param_doc = generate_param_doc(parameters)
    
    # Generate function code
    function_code = f'''
def {operation_id}(**kwargs) -> dict:
    """
    {summary}
    
    {description}
    
    Path: {method.upper()} {path}
    
    Parameters:
{param_doc}
    
    Returns:
        dict: API response with status_code, body, and optional error
    
    Example success:
        {{"status_code": 200, "body": {{"id": 123, "name": "doggie"}}}}
    
    Example error:
        {{"status_code": 404, "body": {{}}, "error": "Pet not found"}}
    
    Note:
        This function is a wrapper that calls ChaosAgent, which may inject
        controlled failures based on failure_rate and seed parameters.
    """
    # This will be implemented to call chaos_agent
    # For now, this is a placeholder that will be replaced with actual implementation
    raise NotImplementedError(
        f"Tool '{{operation_id}}' needs chaos_agent integration. "
        "See chaos_agent_petstore.py for implementation."
    )

'''
    return function_code


def generate_tools_file(swagger_spec: Dict[str, Any], output_file: str) -> None:
    """
    Generate complete Python file with all tool functions.
    
    Args:
        swagger_spec: Parsed Swagger specification
        output_file: Path to output Python file
    """
    print(f"\n📝 Generating tools file: {output_file}")
    
    # Extract all operations from paths
    tools = []
    paths = swagger_spec.get('paths', {})
    
    for path, methods in paths.items():
        for method, spec in methods.items():
            # Skip non-operation keys (like 'parameters')
            if method not in ['get', 'post', 'put', 'delete', 'patch', 'head', 'options']:
                continue
            
            operation_id = spec.get('operationId')
            if not operation_id:
                print(f"   ⚠️  Skipping {method.upper()} {path} - no operationId")
                continue
            
            tool_code = generate_tool_function(operation_id, path, method, spec)
            tools.append({
                'operation_id': operation_id,
                'path': path,
                'method': method,
                'code': tool_code
            })
            
            print(f"   ✅ Generated: {operation_id} ({method.upper()} {path})")
    
    # Generate file header
    header = f'''"""
petstore_tools.py - Auto-generated tool wrappers for Petstore API

AUTO-GENERATED FROM: {swagger_spec.get('info', {}).get('title', 'Unknown API')}
VERSION: {swagger_spec.get('info', {}).get('version', 'Unknown')}
GENERATED ON: 2025-11-26
TOTAL TOOLS: {len(tools)}

DO NOT EDIT THIS FILE MANUALLY - Regenerate using:
    python scripts/generate_tools_from_swagger.py

PURPOSE:
    Each function wraps a Petstore API endpoint and can be used as an ADK tool.
    The actual implementation calls chaos_agent which may inject controlled failures.

USAGE:
    from chaos_playbook_engine.tools.petstore_tools import addPet, getPetById
    
    # These functions will be connected to chaos_agent in the actual implementation
    result = addPet(name="doggie", status="available")
"""

from typing import Dict, Any

# TODO: Import chaos_agent integration
# from chaos_playbook_engine.agents.chaos_agent_petstore import call_chaos_agent


# ============================================================================
# AUTO-GENERATED TOOL FUNCTIONS ({len(tools)} total)
# ============================================================================

'''
    
    # Generate __all__ export list
    all_exports = [tool['operation_id'] for tool in tools]
    exports_code = f"\n__all__ = {all_exports}\n"
    
    # Combine all parts
    file_content = header + exports_code
    for tool in tools:
        file_content += tool['code']
    
    # Add footer
    footer = '''
# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def list_all_tools() -> list:
    """
    Return list of all available tool names.
    
    Returns:
        list: List of operation IDs for all generated tools
    """
    return __all__


def get_tool_info(operation_id: str) -> dict:
    """
    Get information about a specific tool.
    
    Args:
        operation_id: The operation ID of the tool
    
    Returns:
        dict: Tool metadata including docstring
    """
    if operation_id not in __all__:
        raise ValueError(f"Tool '{operation_id}' not found. Available: {__all__}")
    
    tool_func = globals()[operation_id]
    return {
        'operation_id': operation_id,
        'docstring': tool_func.__doc__,
        'signature': str(tool_func.__annotations__)
    }


if __name__ == "__main__":
    print(f"✅ Petstore Tools Module")
    print(f"   Total tools: {len(__all__)}")
    print(f"   Available tools: {', '.join(__all__)}")
'''
    
    file_content += footer
    
    # Write to file
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(file_content)
    
    print(f"\n✅ Successfully generated {len(tools)} tools in {output_file}")
    print(f"   File size: {len(file_content)} bytes")
    print(f"   Tools: {', '.join(all_exports[:5])}{'...' if len(all_exports) > 5 else ''}")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Generate Python tool wrappers from OpenAPI/Swagger specification',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
    # Generate from URL
    python scripts/generate_tools_from_swagger.py \\
        --swagger-url https://petstore3.swagger.io/api/v3/openapi.json \\
        --output src/chaos_playbook_engine/tools/petstore_tools.py
    
    # Generate from local file
    python scripts/generate_tools_from_swagger.py \\
        --swagger-file apis/petstore3_openapi.json \\
        --output src/chaos_playbook_engine/tools/petstore_tools.py
        '''
    )
    
    # Mutually exclusive group for input source
    input_group = parser.add_mutually_exclusive_group(required=True)
    
    input_group.add_argument(
        '--swagger-url',
        type=str,
        help='URL to Swagger/OpenAPI JSON specification'
    )
    
    input_group.add_argument(
        '--swagger-file',
        type=str,
        help='Path to local Swagger/OpenAPI JSON file (e.g., apis/petstore3_openapi.json)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        required=True,
        help='Output Python file path (e.g., src/tools/petstore_tools.py)'
    )
    
    args = parser.parse_args()
    
    try:
        # Step 1: Load Swagger spec (from URL or file)
        swagger_spec = fetch_swagger_spec(
            swagger_url=args.swagger_url,
            swagger_file=args.swagger_file
        )
        
        # Step 2: Generate tools file
        generate_tools_file(swagger_spec, args.output)
        
        print(f"\n🎉 SUCCESS!")
        print(f"   Next step: Implement chaos_agent integration")
        print(f"   Then import tools: from petstore_tools import *")
    
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
