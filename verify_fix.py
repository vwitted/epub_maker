import pypandoc
import os

def test_latex_conversion():
    input_file = 'repro.md'
    output_file = 'repro_test_output.html'
    
    extra_args = [
        '--standalone',
        '--mathml'
    ]
    
    print(f"Converting {input_file} to HTML with --mathml...")
    pypandoc.convert_file(input_file, 'html', outputfile=output_file, extra_args=extra_args)
    
    with open(output_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for MathML tag
    if '<math' in content:
        print("SUCCESS: Found MathML tags in output.")
        
        # Check for specific matrix related tags
        if '<mtable' in content or '<mtr' in content:
            print("SUCCESS: Found matrix-related MathML tags.")
        else:
            print("WARNING: Matrix tags not found, check output content.")
    else:
        print("FAILURE: No MathML tags found in output.")

if __name__ == "__main__":
    if os.path.exists('repro.md'):
        test_latex_conversion()
    else:
        print("repro.md not found.")
