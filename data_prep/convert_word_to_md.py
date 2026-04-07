from pathlib import Path
from markitdown import MarkItDown

INPUT_DIR = Path("workbooks")
OUTPUT_DIR = Path("workbooks_md")

OUTPUT_DIR.mkdir(exist_ok=True)

md = MarkItDown()

docx_files = sorted(INPUT_DIR.glob("*.docx"))
if not docx_files:
    print("No se encontraron archivos .docx en workbooks/")
else:
    for docx_path in docx_files:
        output_path = OUTPUT_DIR / docx_path.with_suffix(".md").name
        result = md.convert(str(docx_path))
        output_path.write_text(result.text_content, encoding="utf-8")
        print(f"Convertido: {docx_path.name} -> {output_path.name}")

    print(f"\nListo: {len(docx_files)} archivo(s) convertidos en {OUTPUT_DIR}/")