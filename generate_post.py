import os

import cloudinary
import cloudinary.uploader
import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

load_dotenv()

FONT_PATH = "Poppins-SemiBold.ttf"

# Each template has its own text box (as fractions of image size) and colour
QUESTION_SLIDE = {
    "template": "postDesign.png",
    "box": (239 / 928, 456 / 1144, 716 / 928, 639 / 1144),
    "colour": (231, 199, 132),
}
ANSWER_SLIDE = {
    "template": "postAnswer.png",
    "box": (165 / 928, 490 / 1152, 762 / 928, 770 / 1152),
    "colour": (247, 231, 164),
}
HEADING_SCALE = 1.5   # "TRUE"/"FALSE" is drawn this much bigger than the explanation

MAX_FONT_SIZE = 44
MIN_FONT_SIZE = 18
LINE_SPACING = 1.25


def _wrap_to_width(text, font, draw, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _fit_text(text, draw, box_w, box_h, heading=None):
    """Find the largest font size where the (optional heading +) wrapped text fits."""
    for size in range(MAX_FONT_SIZE, MIN_FONT_SIZE - 1, -2):
        font = ImageFont.truetype(FONT_PATH, size)
        lines = _wrap_to_width(text, font, draw, box_w)
        line_height = int(size * LINE_SPACING)
        widest = max(draw.textlength(line, font=font) for line in lines)
        heading_font, heading_height = None, 0
        if heading:
            heading_font = ImageFont.truetype(FONT_PATH, int(size * HEADING_SCALE))
            heading_height = int(size * HEADING_SCALE * LINE_SPACING) + size // 2
        if len(lines) * line_height + heading_height <= box_h and widest <= box_w:
            return font, lines, line_height, heading_font, heading_height
    raise ValueError(
        f"Text is too long to fit even at {MIN_FONT_SIZE}px: {text[:40]}... "
        "Shorten it or lower MIN_FONT_SIZE."
    )


def render_image(text, slide, output_path, heading=None):
    """Draw text (and an optional heading line) into a slide's box and save it."""
    text = " ".join(text.split())
    if not text:
        raise ValueError("text is empty")

    img = Image.open(slide["template"]).convert("RGB")
    draw = ImageDraw.Draw(img)

    w, h = img.size
    left, top, right, bottom = (
        slide["box"][0] * w, slide["box"][1] * h,
        slide["box"][2] * w, slide["box"][3] * h,
    )
    box_w, box_h = right - left, bottom - top

    font, lines, line_height, heading_font, heading_height = _fit_text(
        text, draw, box_w, box_h, heading
    )

    y = top + (box_h - len(lines) * line_height - heading_height) / 2
    centre_x = left + box_w / 2
    if heading:
        draw.text((centre_x, y), heading, font=heading_font, fill=slide["colour"], anchor="ma")
        y += heading_height
    for line in lines:
        draw.text((centre_x, y), line, font=font, fill=slide["colour"], anchor="ma")
        y += line_height

    img.save(output_path)
    return output_path


def upload_to_cloudinary(path):
    """Upload an image and return its public HTTPS URL."""
    cloudinary.config(
        cloud_name=os.environ["CLOUDINARY_CLOUD_NAME"],
        api_key=os.environ["CLOUDINARY_API_KEY"],
        api_secret=os.environ["CLOUDINARY_API_SECRET"],
        secure=True,
    )
    result = cloudinary.uploader.upload(
        path,
        folder="dsai/fact-or-fiction",
        resource_type="image",
        format="jpg",
    )
    return result["secure_url"]


def generate_carousel(question, answer_is_true, explanation):
    """Render and upload both slides. Returns (question_url, answer_url)."""
    verdict = "TRUE" if answer_is_true else "FALSE"

    # Render both first, so a too-long explanation fails before anything uploads
    q_path = render_image(question, QUESTION_SLIDE, "output_question.png")
    a_path = render_image(explanation, ANSWER_SLIDE, "output_answer.png", heading=verdict)

    return upload_to_cloudinary(q_path), upload_to_cloudinary(a_path)


def send_to_make(question_url, answer_url, caption=""):
    """Send both slide URLs and the caption to the Make.com webhook."""
    response = requests.post(
        os.environ["MAKE_WEBHOOK_URL"],
        json={
            "question_url": question_url,
            "answer_url": answer_url,
            "caption": caption,
        },
        timeout=30,
    )
    response.raise_for_status()
    print("Sent to Make:", response.status_code, response.text)


if __name__ == "__main__":
    question_url, answer_url = generate_carousel(
        question="Neural networks were first proposed in the 1940s, "
                 "long before modern computers could train them.",
        answer_is_true=True,
        explanation="McCulloch and Pitts described the first mathematical model "
                    "of a neuron in 1943.",
    )
    print("question_url:", question_url)
    print("answer_url:", answer_url)

    caption = (
        "Think you know AI? 🤔 Comment TRUE or FALSE, then swipe to check 👉\n\n"
        "#DataScience #AI #FactOrFiction"
    )
    send_to_make(question_url, answer_url, caption)