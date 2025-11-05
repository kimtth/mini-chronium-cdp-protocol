"""
Mojo .mojom File Parser and Loader

This script directly parses .mojom files and generates Python bindings dynamically.
It reads actual Mojo IDL syntax and creates usable Python classes.
"""

import re
from dataclasses import dataclass
from typing import List
from enum import Enum

@dataclass
class MojomEnum:
    name: str
    values: List[str]

@dataclass
class MojomMethod:
    name: str
    params: List[tuple[str, str]]  # [(type, name), ...]
    returns: List[tuple[str, str]]  # [(type, name), ...]

@dataclass
class MojomInterface:
    name: str
    methods: List[MojomMethod]

@dataclass
class MojomModule:
    name: str
    enums: List[MojomEnum]
    interfaces: List[MojomInterface]

class MojomParser:
    """Parser for .mojom Interface Definition Language files"""
    
    TYPE_MAP = {
        'string': str,
        'int32': int,
        'uint32': int,
        'int64': int,
        'uint64': int,
        'bool': bool,
        'float': float,
        'double': float,
        'uint8': int,
    }
    
    def __init__(self, mojom_content: str):
        self.content = self._remove_comments(mojom_content)
        self.module = None
    
    def _remove_comments(self, content: str) -> str:
        # Remove single-line comments
        content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
        # Remove multi-line comments
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        return content
    
    def parse(self) -> MojomModule:
        module_name = self._parse_module()
        enums = self._parse_enums()
        interfaces = self._parse_interfaces()
        
        self.module = MojomModule(
            name=module_name,
            enums=enums,
            interfaces=interfaces
        )
        return self.module
    
    def _parse_module(self) -> str:
        match = re.search(r'module\s+([\w.]+)\s*;', self.content)
        return match.group(1) if match else "unknown"
    
    def _parse_enums(self) -> List[MojomEnum]:
        enums = []
        enum_pattern = r'enum\s+(\w+)\s*\{([^}]+)\}'
        
        for match in re.finditer(enum_pattern, self.content):
            name = match.group(1)
            body = match.group(2)
            values = [v.strip().rstrip(',') for v in body.split('\n') if v.strip() and not v.strip().startswith('//')]
            enums.append(MojomEnum(name=name, values=values))
        
        return enums
    
    def _parse_interfaces(self) -> List[MojomInterface]:
        interfaces = []
        interface_pattern = r'interface\s+(\w+)\s*\{([^}]+)\}'
        
        for match in re.finditer(interface_pattern, self.content):
            name = match.group(1)
            body = match.group(2)
            methods = self._parse_methods(body)
            interfaces.append(MojomInterface(name=name, methods=methods))
        
        return interfaces
    
    def _parse_methods(self, body: str) -> List[MojomMethod]:
        methods = []
        method_pattern = r'(\w+)\s*\(([^)]*)\)\s*=>\s*\(([^)]*)\)\s*;'
        
        for match in re.finditer(method_pattern, body):
            name = match.group(1)
            params_str = match.group(2)
            returns_str = match.group(3)
            
            params = self._parse_params(params_str)
            returns = self._parse_params(returns_str)
            
            methods.append(MojomMethod(name=name, params=params, returns=returns))
        
        return methods
    
    def _parse_params(self, params_str: str) -> List[tuple[str, str]]:
        if not params_str.strip():
            return []
        
        params = []
        for param in params_str.split(','):
            param = param.strip()
            if param:
                # Handle array types
                if param.startswith('array<'):
                    type_match = re.match(r'array<(\w+)>\s+(\w+)', param)
                    if type_match:
                        params.append((f'array<{type_match.group(1)}>', type_match.group(2)))
                else:
                    parts = param.split()
                    if len(parts) >= 2:
                        params.append((parts[0], parts[1]))
        
        return params

class MojomGenerator:
    """Generates Python classes from parsed .mojom definitions"""
    
    def __init__(self, module: MojomModule):
        self.module = module
        self.generated_classes = {}
    
    def generate(self):
        # Generate enums
        for enum_def in self.module.enums:
            self.generated_classes[enum_def.name] = self._generate_enum(enum_def)
        
        # Generate interface proxies
        for interface in self.module.interfaces:
            proxy_class = self._generate_proxy(interface)
            self.generated_classes[f"{interface.name}Proxy"] = proxy_class
        
        return self.generated_classes
    
    def _generate_enum(self, enum_def: MojomEnum) -> type:
        enum_dict = {value: i for i, value in enumerate(enum_def.values)}
        return Enum(enum_def.name, enum_dict)
    
    def _generate_proxy(self, interface: MojomInterface) -> type:
        """Dynamically generate a proxy class for the interface"""
        
        def __init__(self, message_sender):
            self.message_sender = message_sender
            self.request_id = 0
            self.pending_callbacks = {}
        
        def handle_response(self, response):
            request_id = response["id"]
            if request_id in self.pending_callbacks:
                callback = self.pending_callbacks.pop(request_id)
                callback(response["result"])
        
        # Create methods dynamically
        methods = {
            '__init__': __init__,
            'handle_response': handle_response
        }
        
        for method in interface.methods:
            methods[self._to_snake_case(method.name)] = self._create_method(method)
        
        # Create the class dynamically
        proxy_class = type(
            f"{interface.name}Proxy",
            (),
            methods
        )
        
        return proxy_class
    
    def _create_method(self, method: MojomMethod):
        """Create a method function dynamically"""
        method_name = method.name
        
        def method_func(self, *args, callback=None):
            self.request_id += 1
            
            # Build params dict from args
            params = {}
            for i, (param_type, param_name) in enumerate(method.params):
                if i < len(args):
                    params[param_name] = args[i]
            
            request = {
                "id": self.request_id,
                "method": method_name,
                "params": params
            }
            
            if callback:
                self.pending_callbacks[self.request_id] = callback
            
            self.message_sender(request)
        
        return method_func
    
    def _to_snake_case(self, name: str) -> str:
        """Convert CamelCase to snake_case"""
        return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

def load_mojom(filepath: str):
    """Load and parse a .mojom file, returning generated Python classes"""
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    parser = MojomParser(content)
    module = parser.parse()
    
    generator = MojomGenerator(module)
    classes = generator.generate()
    
    return classes

def main():
    print("🔍 Loading .mojom file...\n")
    
    # Load the .mojom file
    classes = load_mojom("browser_service.mojom")
    
    print("✅ Successfully parsed browser_service.mojom\n")
    print("📦 Generated classes:")
    for name in classes.keys():
        print(f"   • {name}")
    
    # Use the generated classes
    print("\n🎯 Using generated TabState enum:")
    TabState = classes['TabState']
    print(f"   States: {[s.name for s in TabState]}")
    
    print("\n🔗 Using generated BrowserServiceProxy:")
    
    # Create a message channel
    messages = []
    
    BrowserServiceProxy = classes['BrowserServiceProxy']
    proxy = BrowserServiceProxy(lambda msg: messages.append(msg))
    
    # Call methods
    print("\n1️⃣ Calling create_tab()...")
    proxy.create_tab("https://example.com", callback=lambda r: print(f"   ✅ Callback received: {r}"))
    
    if messages:
        print(f"   📤 Sent message: {messages[0]}")
    
    print("\n2️⃣ Calling navigate_tab()...")
    proxy.navigate_tab(1, "https://google.com", callback=lambda r: print(f"   ✅ Callback received: {r}"))
    
    if len(messages) > 1:
        print(f"   📤 Sent message: {messages[1]}")
    
    print("\n✨ Demo completed!")
    print("\n💡 The .mojom file was parsed and Python classes were generated dynamically!")

if __name__ == "__main__":
    main()
