import os
import sys
import subprocess
import argparse
import multiprocessing
from pathlib import Path

def check_pandoc():
    try:
        import pypandoc
        # This will download pandoc if pypandoc_binary is not working or needs it, 
        # but pypandoc_binary usually bundles it.
        # Let's just check version
        version = pypandoc.get_pandoc_version()
        print(f"Pandoc version: {version}")
        return True
    except OSError:
        # Pypandoc might not find the binary
        print("Error: Pandoc not found. Please ensure pypandoc_binary is installed or Pandoc is in your PATH.")
        return False
    except ImportError:
        print("Error: pypandoc module not found.")
        return False

def convert_pdf_to_markdown(pdf_path, output_dir, force_cpu=False, no_ocr=False, workers=30, batch_size=30, smart_ocr=True):
    """
    Runs the marker command line tool to convert PDF to Markdown.
    We use subprocess to call the CLI because marker's python API can be complex to setup inside a single script 
    without handling all the model loading manually. The CLI is robust.
    """
    print(f"--- parsing {pdf_path.name} with Marker ---")
    
    # Construct the command
    # marker_single is the command line entry point for converting a single file
    # Usage: marker_single [OPTIONS] COMPLETED_FILE OUT_DIR
    
    cmd = [
        "marker_single",
        str(pdf_path),
        "--output_dir", str(output_dir),
        "--DocumentExtractor_max_concurrency", str(workers),
        "--PageExtractor_max_concurrency", str(workers),
        "--layout_batch_size", str(batch_size),
    ]

    # If no_ocr is explicitly passed, handle it here OR in the logic below
    # We will handle it dynamically in the run loop for smart_ocr support
    # if no_ocr:
    #     cmd.append("--disable_ocr")
    
    # Environment variables for execution
    env = os.environ.copy()
    if force_cpu:
        env["CUDA_VISIBLE_DEVICES"] = ""
        env["TORCH_DEVICE"] = "cpu"
    
    # Check for device args if user specialized them, otherwise marker auto-detects
    # Marker automatically uses GPU if cuda is available.
    
    try:
        # Remove max_pages restriction for real usage if desired
        # For this prototype we keep it to avoid locking user up for hours on a book
        # But we should probably make it configurable. 
        # Let's actually REMOVE the limit for the script to be useful, 
        # but warn the user.
        # cmd.remove("--max_pages") 
        # cmd.remove("10")
        
        # We need to capture the exact output folder marker creates. 
        # Marker usually creates a subdir matching the filename in the output dir.
        # We need to capture the exact output folder marker creates. 
        # Marker usually creates a subdir matching the filename in the output dir.
        # Check if we should force CPU/no-GPU via environment
        # Logic for Smart OCR:
        # 1. If smart_ocr is True, we force no_ocr=True for the first run.
        # 2. We run the command.
        # 3. We check the output. If it looks bad (empty), we retry with no_ocr=False.
        
        effective_no_ocr = no_ocr
        if smart_ocr:
            effective_no_ocr = True

        run_cmd = list(cmd)
        if effective_no_ocr:
            run_cmd.append("--disable_ocr")

        print(f"Running Marker (OCR={'DISABLED' if effective_no_ocr else 'ENABLED'})...")
        subprocess.run(run_cmd, check=True, capture_output=True, text=True, env=env)
        
        # expected output folder
        doc_name = pdf_path.stem
        result_path = output_dir / doc_name / f"{doc_name}.md"
        
        # Check result quality if smart_ocr was active and we disabled OCR
        if smart_ocr and effective_no_ocr and result_path.exists():
            content = result_path.read_text(encoding='utf-8')
            if len(content.strip()) < 100:
                print(f"Smart OCR: Detected low quality output ({len(content)} chars). Retrying with OCR enabled...")
                # Retry with OCR
                run_cmd = list(cmd) # Original cmd without disable_ocr
                # We do NOT append disable_ocr this time
                
                print("Running Marker (OCR=ENABLED)...")
                subprocess.run(run_cmd, check=True, capture_output=True, text=True, env=env)
        
        if result_path.exists():
            return result_path
        else:
            print(f"Expected output not found at {result_path}")
            # Fallback search
            found = list(output_dir.glob(f"**/{doc_name}.md"))
            if found:
                return found[0]
            return None
            
    except subprocess.CalledProcessError as e:
        print(f"Marker extraction failed: {e}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return None
    except FileNotFoundError:
        print("Error: 'marker_single' command not found. Did you install marker-pdf?")
        return None

def convert_markdown_to_epub(md_file, output_epub_path):
    """
    Uses pypandoc to convert the markdown folder to epub.
    """
    import pypandoc
    
    print(f"--- compiling {md_file.name} to EPUB ---")
    
    # Marker images are relative to the md file. 
    # Pandoc needs to know where to find them. 
    # Usually running pandoc from the directory of the md file works best, 
    # or passing resource path.
    
    # We will invoke pandoc via pypandoc
    try:
        # Extra args for better epub formatting
        extra_args = [
            '--standalone',
            '--resource-path=.',  # Look for images in current dir
            '--mathml',           # Convert TeX math to MathML for EPUB 3
            '--metadata', f'title={md_file.stem}'
        ]
        
        # We need to change cwd to the markdown file's directory so relative image links work
        cwd = os.getcwd()
        os.chdir(md_file.parent)
        
        try:
            output = pypandoc.convert_file(
                str(md_file.name), 
                'epub', 
                outputfile=str(output_epub_path),
                extra_args=extra_args
            )
        finally:
            os.chdir(cwd)
            
        print(f"Successfully created: {output_epub_path}")
        return True
        
    except Exception as e:
        print(f"Pandoc conversion failed: {e}")
        return False

def get_hardware_config():
    """
    Detects hardware (CPU/GPU) and returns suggested workers and batch size.
    """
    # Defaults for a basic system
    cpu_cores = os.cpu_count() or 1
    suggested_workers = cpu_cores
    suggested_batch_size = 1

    try:
        import torch
        if torch.cuda.is_available():
            num_gpus = torch.cuda.device_count()
            total_vram_gb = 0
            for i in range(num_gpus):
                props = torch.cuda.get_device_properties(i)
                total_vram_gb += props.total_memory / (1024**3)
            
            # Marker recommends ~5GB per worker. 
            # Let's be slightly conservative to leave room for the OS and other processes.
            suggested_workers = int(total_vram_gb // 5)
            if suggested_workers < 1:
                suggested_workers = 1
            
            # Batch size can be larger on GPU
            suggested_batch_size = 8
            
            print(f"Hardware Detection: Found {num_gpus} GPU(s) with {total_vram_gb:.1f}GB total VRAM.")
        else:
            print(f"Hardware Detection: No GPU found. Using CPU cores ({cpu_cores}).")
    except ImportError:
        print(f"Hardware Detection: Torch not found. Falling back to CPU cores ({cpu_cores}).")

    return suggested_workers, suggested_batch_size

def main():
    # Detect hardware defaults before parsing args
    default_workers, default_batch_size = get_hardware_config()

    parser = argparse.ArgumentParser(description="Convert PDF to EPUB using Marker and Pandoc")
    parser.add_argument("input", help="Path to PDF file or directory")
    parser.add_argument("--output", help="Output directory (default: same as input)", default=None)
    parser.add_argument("--workers", type=int, default=default_workers, help=f"Number of worker processes/threads (default: {default_workers})")
    parser.add_argument("--batch-size", type=int, default=default_batch_size, help=f"Batch size for layout model (default: {default_batch_size})")
    parser.add_argument("--skip-existing", action="store_true", help="Skip Marker step if md exists (debug)")
    parser.add_argument("--force-cpu", action="store_true", help="Force CPU usage (disable CUDA)")
    parser.add_argument("--no-ocr", action="store_true", help="Disable OCR (pass --disable_ocr to marker)")
    parser.add_argument("--smart-ocr", action="store_true", help="Try without OCR first, fall back to OCR if result is empty")
    
    args = parser.parse_args()
    
    if not check_pandoc():
        return

    input_path = Path(args.input)
    
    if not input_path.exists():
        print(f"Error: {input_path} does not exist")
        return

    # Determine files to process
    files = []
    if input_path.is_file() and input_path.suffix.lower() == '.pdf':
        files.append(input_path)
    elif input_path.is_dir():
        files = list(input_path.glob("*.pdf"))
    
    if not files:
        print("No PDF files found.")
        return
    for pdf in files:
        if pdf.name[:-4] + ".epub" in files:
            files.remove(pdf)
            print(f"Skipping {pdf.name} as {pdf.name[:-4]} already exists.")

    print(f"Found {len(files)} PDFs to process.")

    for pdf in files:
        # Setup output dirs
        base_dir = Path(args.output) if args.output else pdf.parent
        staging_dir = base_dir / "marker_staging"
        staging_dir.mkdir(parents=True, exist_ok=True)
        
        final_epub = base_dir / f"{pdf.stem}.epub"
        
        markdown_file = None
        
        if not args.skip_existing:
            print(f"\nProcessing: {pdf.name}")
            markdown_file = convert_pdf_to_markdown(
                pdf, 
                staging_dir, 
                force_cpu=args.force_cpu, 
                no_ocr=args.no_ocr,
                workers=args.workers,
                batch_size=args.batch_size,
                smart_ocr=args.smart_ocr
            )
        else:
            # Debug mode: verify if file exists
            doc_name = pdf.stem
            possible_path = staging_dir / doc_name / f"{doc_name}.md"
            if possible_path.exists():
                markdown_file = possible_path
            else:
                print("Skipping extraction but markdown file not found in staging.")
        
        if markdown_file:
            success = convert_markdown_to_epub(markdown_file, final_epub)
            if success:
                print(f"DONE. File ready at: {final_epub}")
        else:
            print(f"Skipping EPUB generation for {pdf.name} due to extraction failure.")

if __name__ == "__main__":
    main()