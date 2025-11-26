"""
generate_playbook_from_swagger.py - Auto-generate default playbook from OpenAPI Swagger

USAGE:
    python scripts/generate_playbook_from_swagger.py \\
        --swagger-url https://petstore.swagger.io/v2/swagger.json \\
        --output data/playbook_petstore_default.json

PURPOSE:
    Read Swagger/OpenAPI specification and generate a playbook with sensible
    default retry strategies for each (tool, error_code) combination.

HEURISTICS:
    - 400 (Bad Request): Retry 1x for GET, 0x for POST/PUT (avoid duplicates)
    - 404 (Not Found): Retry 2x for GET, 1x for POST/PUT
    - 405 (Method Not Allowed): No retry (programming error)
    - 500 (Internal Error): Retry 3x with 2s backoff
    - 503 (Service Unavailable): Retry 4x with 3s backoff

AUTHOR: Auto-generated script for chaos-playbook-engine Phase 6
DATE: 2025-11-26
"""

import argparse
import json
import requests
from typing import Dict, List, Any
from pathlib import Path


def fetch_swagger_spec(swagger_url: str) -> Dict[str, Any]:
    """
    Download Swagger/OpenAPI specification from URL.
    
    Args:
        swagger_url: URL to swagger.json or OpenAPI spec
    
    Returns:
        dict: Parsed Swagger specification
    """
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


def get_default_strategy(error_code: int, method: str) -> Dict[str, Any]:
    """
    Get default retry strategy based on HTTP error code and method.
    
    Heuristics:
    - 400 (Bad Request): May be transient validation → Retry 1x for safe methods
    - 404 (Not Found): May be eventual consistency → Retry 2x for safe methods
    - 405 (Method Not Allowed): Programming error → No retry
    - 500 (Internal Error): Server issue → Retry 3x with backoff
    - 503 (Service Unavailable): Temporary → Retry 4x with backoff
    - Safe methods (GET, HEAD): More aggressive retries (idempotent)
    - Unsafe methods (POST, PUT): Conservative retries (avoid duplicates)
    
    Args:
        error_code: HTTP status code (400, 404, 500, etc.)
        method: HTTP method (get, post, put, delete)
    
    Returns:
        dict: Strategy with action, max_retries, backoff_seconds
    """
    is_safe_method = method.upper() in ['GET', 'HEAD', 'OPTIONS']
    
    # Default strategies by error code
    strategies = {
        400: {
            'action': 'retry',
            'max_retries': 1 if is_safe_method else 0,
            'backoff_seconds': 1,
            'reason': 'Transient validation error' if is_safe_method else 'Avoid duplicate writes'
        },
        404: {
            'action': 'retry',
            'max_retries': 2 if is_safe_method else 1,
            'backoff_seconds': 2,
            'reason': 'Eventual consistency delay' if is_safe_method else 'Possible race condition'
        },
        405: {
            'action': 'fail_immediately',
            'max_retries': 0,
            'backoff_seconds': 0,
            'reason': 'Programming error (wrong HTTP method)'
        },
        409: {
            'action': 'retry',
            'max_retries': 1,
            'backoff_seconds': 1,
            'reason': 'Conflict - resource may resolve'
        },
        429: {
            'action': 'retry',
            'max_retries': 3,
            'backoff_seconds': 5,
            'reason': 'Rate limit - exponential backoff'
        },
        500: {
            'action': 'retry',
            'max_retries': 3,
            'backoff_seconds': 2,
            'reason': 'Server error - may recover'
        },
        502: {
            'action': 'retry',
            'max_retries': 2,
            'backoff_seconds': 3,
            'reason': 'Bad gateway - temporary'
        },
        503: {
            'action': 'retry',
            'max_retries': 4,
            'backoff_seconds': 3,
            'reason': 'Service temporarily unavailable'
        },
        504: {
            'action': 'retry',
            'max_retries': 2,
            'backoff_seconds': 5,
            'reason': 'Gateway timeout - slow response'
        }
    }
    
    # Return specific strategy or generic retry
    return strategies.get(
        error_code,
        {
            'action': 'retry',
            'max_retries': 2,
            'backoff_seconds': 1,
            'reason': 'Generic retry strategy'
        }
    )


def extract_error_codes(responses: Dict[str, Any]) -> List[int]:
    """
    Extract error status codes from Swagger responses.
    
    Args:
        responses: Responses object from Swagger operation
    
    Returns:
        list: List of error status codes (400+)
    """
    error_codes = []
    
    for status_code, response_spec in responses.items():
        try:
            code = int(status_code)
            if code >= 400:
                error_codes.append(code)
        except ValueError:
            # Skip 'default' and other non-numeric status codes
            continue
    
    return sorted(error_codes)


def generate_playbook(swagger_spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate playbook with default strategies for all operations.
    
    Args:
        swagger_spec: Parsed Swagger specification
    
    Returns:
        dict: Playbook with procedures for each (tool, error_code)
    """
    print(f"\n📝 Generating playbook procedures...")
    
    procedures = []
    paths = swagger_spec.get('paths', {})
    
    for path, methods in paths.items():
        for method, spec in methods.items():
            # Skip non-operation keys
            if method not in ['get', 'post', 'put', 'delete', 'patch', 'head', 'options']:
                continue
            
            operation_id = spec.get('operationId')
            if not operation_id:
                continue
            
            summary = spec.get('summary', 'No summary')
            responses = spec.get('responses', {})
            error_codes = extract_error_codes(responses)
            
            if not error_codes:
                print(f"   ⚠️  {operation_id}: No error codes documented in Swagger")
                # Add common errors anyway (400, 404, 500)
                error_codes = [400, 404, 500]
            
            # Generate procedure for each error code
            for error_code in error_codes:
                error_description = responses.get(str(error_code), {}).get('description', 'No description')
                strategy = get_default_strategy(error_code, method)
                
                procedure = {
                    'tool': operation_id,
                    'error_code': str(error_code),
                    'error_description': error_description,
                    'action': strategy['action'],
                    'max_retries': strategy['max_retries'],
                    'backoff_seconds': strategy['backoff_seconds'],
                    'reason': strategy['reason'],
                    'http_method': method.upper(),
                    'api_path': path
                }
                
                procedures.append(procedure)
                
                action_str = f"{strategy['action']} (retries={strategy['max_retries']})"
                print(f"   ✅ {operation_id} + {error_code}: {action_str}")
    
    # Create playbook structure
    playbook = {
        '_metadata': {
            'generated_from': swagger_spec.get('info', {}).get('title', 'Unknown API'),
            'api_version': swagger_spec.get('info', {}).get('version', 'Unknown'),
            'generated_on': '2025-11-26',
            'total_procedures': len(procedures),
            'description': 'Auto-generated playbook with default retry strategies based on HTTP status codes and methods'
        },
        'procedures': procedures
    }
    
    return playbook


def save_playbook(playbook: Dict[str, Any], output_file: str) -> None:
    """
    Save playbook to JSON file.
    
    Args:
        playbook: Generated playbook dict
        output_file: Path to output JSON file
    """
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(playbook, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Successfully saved playbook to {output_file}")
    print(f"   Total procedures: {playbook['_metadata']['total_procedures']}")
    
    # Print summary statistics
    actions_count = {}
    for proc in playbook['procedures']:
        action = proc['action']
        actions_count[action] = actions_count.get(action, 0) + 1
    
    print(f"\n📊 Strategy Distribution:")
    for action, count in sorted(actions_count.items()):
        print(f"   - {action}: {count} procedures")


def generate_playbook_variations(base_playbook: Dict[str, Any], output_dir: str) -> None:
    """
    Generate additional playbook variations (aggressive, conservative).
    
    Args:
        base_playbook: Base playbook with default strategies
        output_dir: Directory to save variation files
    """
    print(f"\n📝 Generating playbook variations...")
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Aggressive playbook: Max retries, longer backoff
    aggressive = {
        '_metadata': {
            **base_playbook['_metadata'],
            'variant': 'aggressive',
            'description': 'Aggressive retry strategy - maximizes success rate at cost of latency'
        },
        'procedures': []
    }
    
    for proc in base_playbook['procedures']:
        aggressive_proc = proc.copy()
        if proc['action'] == 'retry':
            aggressive_proc['max_retries'] = min(proc['max_retries'] + 2, 5)
            aggressive_proc['backoff_seconds'] = proc['backoff_seconds'] + 1
        aggressive['procedures'].append(aggressive_proc)
    
    aggressive_file = output_path / 'playbook_petstore_aggressive.json'
    with open(aggressive_file, 'w', encoding='utf-8') as f:
        json.dump(aggressive, f, indent=2, ensure_ascii=False)
    print(f"   ✅ Saved: {aggressive_file}")
    
    # Conservative playbook: Min retries, shorter backoff
    conservative = {
        '_metadata': {
            **base_playbook['_metadata'],
            'variant': 'conservative',
            'description': 'Conservative retry strategy - minimizes latency at cost of success rate'
        },
        'procedures': []
    }
    
    for proc in base_playbook['procedures']:
        conservative_proc = proc.copy()
        if proc['action'] == 'retry' and proc['max_retries'] > 0:
            conservative_proc['max_retries'] = max(proc['max_retries'] - 1, 0)
            conservative_proc['backoff_seconds'] = max(proc['backoff_seconds'] - 1, 0)
        conservative['procedures'].append(conservative_proc)
    
    conservative_file = output_path / 'playbook_petstore_conservative.json'
    with open(conservative_file, 'w', encoding='utf-8') as f:
        json.dump(conservative, f, indent=2, ensure_ascii=False)
    print(f"   ✅ Saved: {conservative_file}")
    
    # No playbook: All failures immediately (for comparison)
    no_playbook = {
        '_metadata': {
            **base_playbook['_metadata'],
            'variant': 'no_retries',
            'description': 'Baseline - no retries, fail immediately (for comparison)'
        },
        'procedures': []
    }
    
    for proc in base_playbook['procedures']:
        no_retry_proc = proc.copy()
        no_retry_proc['action'] = 'fail_immediately'
        no_retry_proc['max_retries'] = 0
        no_retry_proc['backoff_seconds'] = 0
        no_playbook['procedures'].append(no_retry_proc)
    
    no_playbook_file = output_path / 'playbook_petstore_no_retries.json'
    with open(no_playbook_file, 'w', encoding='utf-8') as f:
        json.dump(no_playbook, f, indent=2, ensure_ascii=False)
    print(f"   ✅ Saved: {no_playbook_file}")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Generate default playbook from OpenAPI/Swagger specification',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
    # Generate default playbook
    python scripts/generate_playbook_from_swagger.py \\
        --swagger-url https://petstore.swagger.io/v2/swagger.json \\
        --output data/playbook_petstore_default.json
    
    # Generate with variations
    python scripts/generate_playbook_from_swagger.py \\
        --swagger-url https://petstore.swagger.io/v2/swagger.json \\
        --output data/playbook_petstore_default.json \\
        --generate-variations
        '''
    )
    
    parser.add_argument(
        '--swagger-url',
        type=str,
        required=True,
        help='URL to Swagger/OpenAPI JSON specification'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        required=True,
        help='Output JSON file path (e.g., data/playbook_petstore_default.json)'
    )
    
    parser.add_argument(
        '--generate-variations',
        action='store_true',
        help='Generate additional playbook variations (aggressive, conservative, no_retries)'
    )
    
    args = parser.parse_args()
    
    try:
        # Step 1: Download Swagger spec
        swagger_spec = fetch_swagger_spec(args.swagger_url)
        
        # Step 2: Generate playbook
        playbook = generate_playbook(swagger_spec)
        
        # Step 3: Save playbook
        save_playbook(playbook, args.output)
        
        # Step 4: Generate variations if requested
        if args.generate_variations:
            output_dir = Path(args.output).parent
            generate_playbook_variations(playbook, str(output_dir))
        
        print(f"\n🎉 SUCCESS!")
        print(f"   Playbook ready to use with OrderAgent")
        print(f"\n   Next step: Integrate with chaos_agent_petstore.py")
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
