#!/usr/bin/env python3
"""Convierte el informe Markdown a PDF con estilo similar al original."""
import re
import markdown
from weasyprint import HTML, CSS

SRC = "Informe TFI - Torreta-Escaner 3D - UTN FRSR 2026.md"
OUT = "Informe TFI - Torreta-Escaner 3D - UTN FRSR 2026.pdf"

with open(SRC, encoding="utf-8") as f:
    text = f.read()

# Separar la portada (todo lo previo al primer "## Resumen") para maquetarla aparte
parts = text.split("## Resumen", 1)
portada_md = parts[0]
cuerpo_md = "## Resumen" + parts[1] if len(parts) > 1 else text

md = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "attr_list", "sane_lists"])
portada_html = md.convert(portada_md)
md.reset()
cuerpo_html = md.convert(cuerpo_md)

html = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"></head>
<body>
  <section class="portada">{portada_html}</section>
  <section class="cuerpo">{cuerpo_html}</section>
</body></html>"""

css = CSS(string=r"""
@page {
  size: A4;
  margin: 2.2cm 2cm 2.2cm 2cm;
  @top-left  { content: "UTN FRSR — Ingeniería en Sistemas"; font-size: 8.5pt; color: #888; }
  @top-right { content: "Arduino — Trabajo Final Integrador"; font-size: 8.5pt; color: #888; }
  @bottom-center { content: "Página " counter(page) " de " counter(pages); font-size: 8.5pt; color: #888; }
}
@page :first { @top-left { content: ""; } @top-right { content: ""; } @bottom-center { content: ""; } }

body { font-family: "Georgia", "Times New Roman", serif; font-size: 10.5pt; line-height: 1.5; color: #1c1c1c; text-align: justify; }

.portada { text-align: center; height: 24cm; display: flex; flex-direction: column; justify-content: center; page-break-after: always; }
.portada h1 { font-size: 26pt; color: #1d3b5e; border: none; margin: 0.3cm 0; }
.portada h3 { font-size: 13pt; color: #34557a; font-style: italic; font-weight: normal; border: none; margin: 0.2cm 1.5cm 0.6cm; }
.portada p { font-size: 11pt; color: #333; }
.portada hr { width: 40%; margin: 0.6cm auto; border: none; border-top: 1.5px solid #1d3b5e; }

h1 { font-size: 19pt; color: #1d3b5e; border-bottom: 2px solid #1d3b5e; padding-bottom: 4px; margin-top: 1.0cm; page-break-after: avoid; }
h2 { font-size: 14pt; color: #234e7d; margin-top: 0.7cm; page-break-after: avoid; }
h3 { font-size: 11.5pt; color: #2f5b8c; page-break-after: avoid; }
p { margin: 0.25cm 0; }

table { border-collapse: collapse; width: 100%; margin: 0.4cm 0; font-size: 9.5pt; }
th { background: #e7eef6; color: #1d3b5e; text-align: left; padding: 5px 8px; border: 1px solid #b9c8da; }
td { padding: 5px 8px; border: 1px solid #cdd6e0; vertical-align: top; }
tr:nth-child(even) td { background: #f7f9fc; }

pre { background: #f4f6f8; border: 1px solid #dde3ea; border-left: 3px solid #234e7d; border-radius: 3px;
      padding: 8px 12px; font-family: "DejaVu Sans Mono", monospace; font-size: 8.6pt; line-height: 1.35;
      white-space: pre-wrap; word-wrap: break-word; page-break-inside: avoid; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: 9pt; background: #eef1f4; padding: 0 3px; border-radius: 2px; }
pre code { background: none; padding: 0; }

blockquote { border-left: 3px solid #c9a23a; background: #fbf6e7; margin: 0.4cm 0; padding: 6px 14px; color: #5b4a1a; }
hr { border: none; border-top: 1px solid #d4d4d4; margin: 0.6cm 0; }
strong { color: #1c1c1c; }
em { color: #333; }
ul, ol { margin: 0.2cm 0 0.2cm 0.2cm; }
li { margin: 0.12cm 0; }
""")

HTML(string=html, base_url=".").write_pdf(OUT, stylesheets=[css])
print("PDF generado:", OUT)
