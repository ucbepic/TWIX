
from typing import Optional

from google.api_core.client_options import ClientOptions
from google.cloud import documentai  # type: ignore

# TODO(developer): Uncomment these variables before running the sample.
# project_id = "YOUR_PROJECT_ID"
# location = "YOUR_PROCESSOR_LOCATION" # Format is "us" or "eu"
# processor_id = "YOUR_PROCESSOR_ID" # Create processor before running sample
# file_path = "/path/to/local/pdf"
# mime_type = "application/pdf" # Refer to https://cloud.google.com/document-ai/docs/file-types for supported file types
# field_mask = "text,entities,pages.pageNumber"  # Optional. The fields to return in the Document object.
# processor_version_id = "YOUR_PROCESSOR_VERSION_ID" # Optional. Processor version to use
from typing import Optional, Sequence

from google.api_core.client_options import ClientOptions
from google.cloud import documentai
import os 
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/Users/yiminglin/.config/gcloud/application_default_credentials.json'




# TODO(developer): Uncomment these variables before running the sample.
# project_id = "YOUR_PROJECT_ID"
# location = "YOUR_PROCESSOR_LOCATION" # Format is "us" or "eu"
# processor_id = "YOUR_PROCESSOR_ID" # Create processor before running sample
# processor_version = "rc" # Refer to https://cloud.google.com/document-ai/docs/manage-processor-versions for more information
# file_path = "/path/to/local/pdf"
# mime_type = "application/pdf" # Refer to https://cloud.google.com/document-ai/docs/file-types for supported file types


def process_document_ocr_sample(
    project_id="392558858304",
    location="us",
    processor_id="b442d49df3d75a43",
    file_path="/Users/yiminglin/Documents/Codebase/Pdf_reverse/data/raw/certification/CT/DecertifiedOfficersRev_9622 Emilie Munson.pdf",
    mime_type="application/pdf",
    processor_version = 'pretrained-ocr-v2.0-2023-06-02'
) -> None:
    # Optional: Additional configurations for Document OCR Processor.
    # For more information: https://cloud.google.com/document-ai/docs/enterprise-document-ocr
    process_options = documentai.ProcessOptions(
        ocr_config=documentai.OcrConfig(
            enable_native_pdf_parsing=True,
            enable_image_quality_scores=True,
            enable_symbol=True,
            # OCR Add Ons https://cloud.google.com/document-ai/docs/ocr-add-ons
            premium_features=documentai.OcrConfig.PremiumFeatures(
                compute_style_info=True,
                enable_math_ocr=False,  # Enable to use Math OCR Model
                enable_selection_mark_detection=True,
            ),
        )
    )
    # Online processing request to Document AI
    document = process_document(
        project_id,
        location,
        processor_id,
        processor_version,
        file_path,
        mime_type,
        process_options=process_options,
    )

    text = document.text
    print(f"Full document text: {text}\n")
    print(f"There are {len(document.pages)} page(s) in this document.\n")

    for page in document.pages:
        print(f"Page {page.page_number}:")
        print_page_dimensions(page.dimension)
        print_detected_languages(page.detected_languages)

        print_blocks(page.blocks, text)
        print_paragraphs(page.paragraphs, text)
        print_lines(page.lines, text)
        print_tokens(page.tokens, text)

        if page.symbols:
            print_symbols(page.symbols, text)

        if page.image_quality_scores:
            print_image_quality_scores(page.image_quality_scores)

        if page.visual_elements:
            print_visual_elements(page.visual_elements, text)


def print_page_dimensions(dimension: documentai.Document.Page.Dimension) -> None:
    print(f"    Width: {str(dimension.width)}")
    print(f"    Height: {str(dimension.height)}")


def print_detected_languages(
    detected_languages: Sequence[documentai.Document.Page.DetectedLanguage],
) -> None:
    print("    Detected languages:")
    for lang in detected_languages:
        print(f"        {lang.language_code} ({lang.confidence:.1%} confidence)")


def print_blocks(blocks: Sequence[documentai.Document.Page.Block], text: str) -> None:
    print(f"    {len(blocks)} blocks detected:")
    first_block_text = layout_to_text(blocks[0].layout, text)
    print(f"        First text block: {repr(first_block_text)}")
    last_block_text = layout_to_text(blocks[-1].layout, text)
    print(f"        Last text block: {repr(last_block_text)}")


def print_paragraphs(
    paragraphs: Sequence[documentai.Document.Page.Paragraph], text: str
) -> None:
    print(f"    {len(paragraphs)} paragraphs detected:")
    first_paragraph_text = layout_to_text(paragraphs[0].layout, text)
    print(f"        First paragraph text: {repr(first_paragraph_text)}")
    last_paragraph_text = layout_to_text(paragraphs[-1].layout, text)
    print(f"        Last paragraph text: {repr(last_paragraph_text)}")


def print_lines(lines: Sequence[documentai.Document.Page.Line], text: str) -> None:
    print(f"    {len(lines)} lines detected:")
    first_line_text = layout_to_text(lines[0].layout, text)
    print(f"        First line text: {repr(first_line_text)}")
    last_line_text = layout_to_text(lines[-1].layout, text)
    print(f"        Last line text: {repr(last_line_text)}")


def print_tokens(tokens: Sequence[documentai.Document.Page.Token], text: str) -> None:
    print(f"    {len(tokens)} tokens detected:")
    first_token_text = layout_to_text(tokens[0].layout, text)
    first_token_break_type = tokens[0].detected_break.type_.name
    print(f"        First token text: {repr(first_token_text)}")
    print(f"        First token break type: {repr(first_token_break_type)}")
    if tokens[0].style_info:
        print_style_info(tokens[0].style_info)

    last_token_text = layout_to_text(tokens[-1].layout, text)
    last_token_break_type = tokens[-1].detected_break.type_.name
    print(f"        Last token text: {repr(last_token_text)}")
    print(f"        Last token break type: {repr(last_token_break_type)}")
    if tokens[-1].style_info:
        print_style_info(tokens[-1].style_info)


def print_symbols(
    symbols: Sequence[documentai.Document.Page.Symbol], text: str
) -> None:
    print(f"    {len(symbols)} symbols detected:")
    first_symbol_text = layout_to_text(symbols[0].layout, text)
    print(f"        First symbol text: {repr(first_symbol_text)}")
    last_symbol_text = layout_to_text(symbols[-1].layout, text)
    print(f"        Last symbol text: {repr(last_symbol_text)}")


def print_image_quality_scores(
    image_quality_scores: documentai.Document.Page.ImageQualityScores,
) -> None:
    print(f"    Quality score: {image_quality_scores.quality_score:.1%}")
    print("    Detected defects:")

    for detected_defect in image_quality_scores.detected_defects:
        print(f"        {detected_defect.type_}: {detected_defect.confidence:.1%}")


def print_style_info(style_info: documentai.Document.Page.Token.StyleInfo) -> None:
    """
    Only supported in version `pretrained-ocr-v2.0-2023-06-02`
    """
    print(f"           Font Size: {style_info.font_size}pt")
    print(f"           Font Type: {style_info.font_type}")
    print(f"           Bold: {style_info.bold}")
    print(f"           Italic: {style_info.italic}")
    print(f"           Underlined: {style_info.underlined}")
    print(f"           Handwritten: {style_info.handwritten}")
    print(
        f"           Text Color (RGBa): {style_info.text_color.red}, {style_info.text_color.green}, {style_info.text_color.blue}, {style_info.text_color.alpha}"
    )


def print_visual_elements(
    visual_elements: Sequence[documentai.Document.Page.VisualElement], text: str
) -> None:
    """
    Only supported in version `pretrained-ocr-v2.0-2023-06-02`
    """
    checkboxes = [x for x in visual_elements if "checkbox" in x.type]
    math_symbols = [x for x in visual_elements if x.type == "math_formula"]

    if checkboxes:
        print(f"    {len(checkboxes)} checkboxes detected:")
        print(f"        First checkbox: {repr(checkboxes[0].type)}")
        print(f"        Last checkbox: {repr(checkboxes[-1].type)}")

    if math_symbols:
        print(f"    {len(math_symbols)} math symbols detected:")
        first_math_symbol_text = layout_to_text(math_symbols[0].layout, text)
        print(f"        First math symbol: {repr(first_math_symbol_text)}")




def process_document(
    project_id: str,
    location: str,
    processor_id: str,
    processor_version: str,
    file_path: str,
    mime_type: str,
    process_options: Optional[documentai.ProcessOptions] = None,
) -> documentai.Document:
    # You must set the `api_endpoint` if you use a location other than "us".
    client = documentai.DocumentProcessorServiceClient(
        client_options=ClientOptions(
            api_endpoint=f"{location}-documentai.googleapis.com"
        )
    )

    # The full resource name of the processor version, e.g.:
    # `projects/{project_id}/locations/{location}/processors/{processor_id}/processorVersions/{processor_version_id}`
    # You must create a processor before running this sample.
    name = client.processor_version_path(
        project_id, location, processor_id, processor_version
    )

    # Read the file into memory
    with open(file_path, "rb") as image:
        image_content = image.read()

    # Configure the process request
    request = documentai.ProcessRequest(
        name=name,
        raw_document=documentai.RawDocument(content=image_content, mime_type=mime_type),
        # Only supported for Document OCR processor
        process_options=process_options,
    )

    result = client.process_document(request=request)

    # For a full list of `Document` object attributes, reference this page:
    # https://cloud.google.com/document-ai/docs/reference/rest/v1/Document
    return result.document




def layout_to_text(layout: documentai.Document.Page.Layout, text: str) -> str:
    """
    Document AI identifies text in different parts of the document by their
    offsets in the entirety of the document"s text. This function converts
    offsets to a string.
    """
    # If a text segment spans several lines, it will
    # be stored in different text segments.
    return "".join(
        text[int(segment.start_index) : int(segment.end_index)]
        for segment in layout.text_anchor.text_segments
    )


if __name__ == "__main__":
    process_document_ocr_sample()