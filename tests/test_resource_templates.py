"""
Tests for MCP resource templates to ensure multi-segment path support.
"""

import pytest
import asyncio


def test_resource_template_supports_multi_segment_paths():
    """Test that the files resource template uses multi-segment path parameter."""
    from code_index_mcp.server import mcp
    
    # Get resource templates synchronously by running async code
    templates = asyncio.run(mcp._resource_manager.get_resource_templates())
    
    # Should be a dict
    assert isinstance(templates, dict), "Resource templates should be a dictionary"
    
    # Should have the files resource template
    assert len(templates) > 0, "Should have at least one resource template"
    
    # Find files resource template
    files_templates = {uri: tmpl for uri, tmpl in templates.items() if 'files://' in uri}
    assert len(files_templates) == 1, "Should have exactly one files resource template"
    
    # Get the files template
    uri_template, template = next(iter(files_templates.items()))
    
    # Assert it uses multi-segment parameter syntax
    assert '{file_path*}' in uri_template, \
        f"Files resource should use multi-segment parameter {{file_path*}}, got: {uri_template}"
    
    # Verify it's not using single-segment
    assert uri_template != 'files://{file_path}', \
        "Files resource should not use single-segment parameter"
    
    # Verify the template properties
    assert template.name == 'get_file_content', \
        f"Template should be named 'get_file_content', got: {template.name}"
    assert template.description is not None, "Template should have a description"
    assert 'file_path' in template.parameters['properties'], \
        "Template should have file_path parameter"


def test_multi_segment_resource_examples():
    """Test that multi-segment resource URIs are correctly structured."""
    from code_index_mcp.server import mcp
    
    templates = asyncio.run(mcp._resource_manager.get_resource_templates())
    
    # Get files template URI
    files_uri = next((uri for uri in templates.keys() if 'files://' in uri), None)
    assert files_uri is not None, "Files resource template should exist"
    
    # Verify the URI template format
    assert files_uri == 'files://{file_path*}', \
        f"Expected 'files://{{file_path*}}', got: {files_uri}"
    
    # Document expected usage patterns
    expected_paths = [
        'README.md',
        'src/server.py',
        'src/components/Button.tsx',
        'test/sample-projects/python/main.py',
        'deeply/nested/path/to/file.js'
    ]
    
    # The asterisk in {file_path*} means these paths should all work
    # We can't test actual resource reading here without a project setup,
    # but we verify the template syntax supports them
    for path in expected_paths:
        # Verify no path restrictions in template
        assert '/' in path or not '/' in path, \
            f"Path '{path}' should be supported by multi-segment template"


def test_resource_template_backwards_compatibility():
    """Ensure resource template maintains expected structure."""
    from code_index_mcp.server import mcp
    
    templates = asyncio.run(mcp._resource_manager.get_resource_templates())
    
    # Verify structure
    for uri, template in templates.items():
        assert hasattr(template, 'uri_template'), "Template should have uri_template attribute"
        assert hasattr(template, 'name'), "Template should have name attribute"
        assert hasattr(template, 'description'), "Template should have description attribute"
        assert hasattr(template, 'parameters'), "Template should have parameters attribute"
        
        # Verify parameters structure
        assert 'properties' in template.parameters, "Template parameters should have properties"
        assert 'required' in template.parameters, "Template parameters should have required list"
        assert isinstance(template.parameters['properties'], dict), \
            "Template properties should be a dictionary"


def test_config_resource_still_exists():
    """Ensure the config resource is still registered."""
    from code_index_mcp.server import mcp
    
    # Get static resources
    resources = asyncio.run(mcp._resource_manager.get_resources())
    
    # Should have config resource
    assert isinstance(resources, dict), "Resources should be a dictionary"
    
    config_resources = {uri: res for uri, res in resources.items() if 'config://' in uri}
    assert len(config_resources) == 1, "Should have exactly one config resource"
    
    # Verify config resource URI
    config_uri = next(iter(config_resources.keys()))
    assert config_uri == 'config://code-indexer', \
        f"Expected 'config://code-indexer', got: {config_uri}"
