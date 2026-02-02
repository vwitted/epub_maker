import re

def fix_latex_math(content):
    # 1. Handle \rm followed by braced text: \rm {text} -> \mathrm{text}
    content = re.sub(r'\\rm\s*\{([^}]+)\}', r'\\mathrm{\1}', content)
    # 2. Handle \rm followed by unbraced text: \rm text -> \mathrm{text}
    content = re.sub(r'\\rm\s*([a-zA-Z0-9]+)', r'\\mathrm{\1}', content)
    # 3. Handle any remaining \rm
    content = content.replace(r'\rm', r'\mathrm')
    # 4. Fix array definitions with excessive columns or missing closing brace
    def fix_array(match):
        spec = match.group(1)
        if '{' in spec and '}' not in spec:
            return match.group(0) + '}'
        return match.group(0)
    content = re.sub(r'(\\begin\{array\}\{[c|l|r]+)', fix_array, content)
    # 5. Filter out code snippets incorrectly identified as math
    code_patterns = [r'printf\s*\(', r'fprintf\s*\(', r'cout\s*<<', r'System\.out\.print', r'console\.log\s*\(']
    for pattern in code_patterns:
        content = re.sub(f'\\$(\\$?)([^$]*?{pattern}.*?)\\1\\$', r'\2', content, flags=re.DOTALL)
    # 6. Fix trailing backslashes in math blocks
    content = re.sub(r'\\\\\s*\\\)', r' \\)', content)
    content = re.sub(r'\\\\\s*\\\]', r' \\]', content)
    content = re.sub(r'(\\+)\s*\\\)', r' \)', content)
    content = re.sub(r'(\\+)\s*\\\]', r' \]', content)
    return content

test_cases = {
    "long_array": r"$$ \begin{array}{cccccccccccccccccccccccccccccccccccc $$",
    "printf_math": r'$printf("Sum = %d", x)$',
    "trailing_backslash": r"\( X(s) = G_2(s)\{G_1(s)[R(s)-H(s)X(s)] + D(s)\}\ \)"
}

for name, content in test_cases.items():
    fixed = fix_latex_math(content)
    print(f"CASE: {name}")
    print(f"  ORIG: {content}")
    print(f"  FIXD: {fixed}")
    print("-" * 20)
