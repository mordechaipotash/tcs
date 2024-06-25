import os
import json
import base64
from flask import Flask, request, render_template, jsonify, send_from_directory
from PyPDF2 import PdfReader
from PIL import Image
import requests
import logging
import io
import pdf2image
import uuid

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# API keys
anthropic_api_key = "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"
openrouter_api_key = "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"

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max-limit

# Explicitly set poppler path
POPPLER_PATH = '/opt/homebrew/bin'  # This is the default path for Homebrew installations on macOS

# Model pricing information
MODEL_PRICES = {
    "claude-3.5-sonnet": {"input": 0.000003, "output": 0.000015},  # $3/MTok input, $15/MTok output
    "gpt-4o": {"input": 0.000005, "output": 0.000015}  # $5/MTok input, $15/MTok output
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def pdf_to_images(pdf_path):
    logging.info(f"Converting PDF to images: {pdf_path}")
    images = []
    image_paths = []
    
    try:
        pdf_images = pdf2image.convert_from_path(pdf_path, poppler_path=POPPLER_PATH)
        for i, img in enumerate(pdf_images):
            img_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_image_{uuid.uuid4()}.png")
            img.save(img_path, "PNG")
            images.append(img)
            image_paths.append(img_path)
        logging.info(f"Successfully converted PDF to {len(images)} images using pdf2image")
        return images, image_paths
    except Exception as e:
        logging.error(f"Error converting PDF to images with pdf2image: {str(e)}")
        raise ValueError(f"Failed to extract images from PDF. Error: {str(e)}")

def get_instructions(form_type):
    if form_type == "form1":
        return """
        Analyze this form image and extract the information into the following JSON structure:
        {
          "form_info": {
            "form_number": "",
            "form_title": ""
          },
          "personal_info": {
            "name": "",
            "ssn": "",
            "street_address": "",
            "city_state_zip": "",
            "county": "",
            "telephone": "",
            "date_of_birth": ""
          },
          "questions": [
            {"number": 1, "question": "Have you worked for this employer before?", "answer": ""},
            {"number": 2, "question": "Are you a member of a family that received SNAP benefits during the past 6 months?", "answer": ""},
            {"number": 3, "question": "Are you a member of a family that received TANF/Welfare for the last 18 months before you were hired?", "answer": ""},
            {"number": 4, "question": "Did you receive Supplemental Security Income (SSI) benefits for any month ending within 60 days before you were hired?", "answer": ""},
            {"number": 5, "question": "Were you Unemployed for the past 27 weeks and you received any unemployment benefits?", "answer": ""},
            {"number": 6, "question": "Were you referred by a rehabilitation agency, an employment network under the Ticket to Work program, or the Department of Veterans Affairs?", "answer": ""},
            {"number": 7, "question": "Were you convicted of a felony or released from prison after a felony conviction during the past year?", "answer": ""},
            {"number": 8, "question": "Are you a veteran of the U.S. Armed Forces?", "answer": ""}
          ],
          "signature_date": ""
        }
        Fill in the values based on the information in the image. For yes/no questions, use 'Yes' or 'No' as the answer. If a field is empty or information is not available, leave it as an empty string.
        """
    elif form_type == "form2":
        return """
        Analyze this form image and extract the information into the following JSON structure:
        {
          "form_info": {
            "form_number": "",
            "form_title": ""
          },
          "personal_info": {
            "name": "",
            "ssn": "",
            "street_address": "",
            "city_state_zip": "",
            "county": "",
            "telephone": "",
            "date_of_birth": ""
          },
          "questions": [
            {"number": 1, "question": "Have you worked for this employer before?", "answer": ""},
            {"number": 2, "question": "Are you a member of a family that received SNAP benefits?", "answer": ""},
            {"number": 3, "question": "Are you a member of a family that received TANF/Welfare?", "answer": ""},
            {"number": 4, "question": "Did you receive Supplemental Security Income (SSI) benefits?", "answer": ""},
            {"number": 5, "question": "Were you Unemployed for the past 27 weeks and received unemployment benefits?", "answer": ""},
            {"number": 6, "question": "Were you referred by a rehabilitation agency or employment network?", "answer": ""},
            {"number": 7, "question": "Were you convicted of a felony or released from prison after a felony conviction?", "answer": ""},
            {"number": 8, "question": "Are you a veteran of the U.S. Armed Forces?", "answer": ""}
          ],
          "signature_date": ""
        }
        Fill in the values based on the information in the image. For yes/no questions, use 'Yes' or 'No' as the answer. If a field is empty or information is not available, leave it as an empty string.
        """
    else:
        return "Please analyze this form and extract all relevant information."

def calculate_image_cost(image, model):
    width, height = image.size
    if model == "claude-3.5-sonnet":
        image_tokens = (width * height) / 750
        input_cost = image_tokens * MODEL_PRICES[model]["input"]
    elif model == "gpt-4o":
        tiles = ((width + 511) // 512) * ((height + 511) // 512)
        base_tokens = 85
        tile_tokens = 170 * tiles
        total_tokens = base_tokens + tile_tokens
        input_cost = total_tokens * MODEL_PRICES[model]["input"] / 1000000  # Convert to millions of tokens
    return input_cost

def analyze_image(img, form_type):
    logging.info(f"Analyzing image for form type: {form_type}")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    base64_image = base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')

    instructions = get_instructions(form_type)
    
    models = ["claude-3.5-sonnet", "gpt-4o"]
    results = {}

    for model in models:
        if model == "claude-3.5-sonnet":
            headers = {
                "Content-Type": "application/json",
                "x-api-key": anthropic_api_key,
                "anthropic-version": "2023-06-01"
            }
            payload = {
                "model": "claude-3.5-sonnet-20240320",
                "max_tokens": 4000,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": base64_image
                                }
                            },
                            {
                                "type": "text",
                                "text": instructions
                            }
                        ]
                    }
                ]
            }
            api_url = "https://api.anthropic.com/v1/messages"
        elif model == "gpt-4o":
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {openrouter_api_key}",
                "HTTP-Referer": "http://localhost:5000",  # Replace with your actual site URL
                "X-Title": "PDF Form Extractor"  # Replace with your actual site name
            }
            payload = {
                "model": "openai/gpt-4o",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            },
                            {
                                "type": "text",
                                "text": instructions
                            }
                        ]
                    }
                ]
            }
            api_url = "https://openrouter.ai/api/v1/chat/completions"
        
        try:
            response = requests.post(api_url, headers=headers, json=payload)
            response.raise_for_status()
            
            if model == "claude-3.5-sonnet":
                content = response.json()['content'][0]['text']
            elif model == "gpt-4o":
                content = response.json()['choices'][0]['message']['content']
            
            logging.debug(f"Raw API response for {model}: {content}")
            
            # Calculate input cost
            input_cost = calculate_image_cost(img, model)
            
            # Try to find JSON content within the response
            try:
                start_index = content.index('{')
                end_index = content.rindex('}') + 1
                json_content = json.loads(content[start_index:end_index])
                
                # Calculate output cost (assuming 4 tokens per word as a rough estimate)
                output_tokens = len(content.split()) * 4
                output_cost = output_tokens * MODEL_PRICES[model]["output"] / 1000000  # Convert to millions of tokens
                
                results[model] = {
                    "extracted_data": json_content,
                    "costs": {
                        "input": input_cost,
                        "output": output_cost,
                        "total": input_cost + output_cost
                    }
                }
            except ValueError:
                logging.error(f"Could not find valid JSON in the API response for {model}")
                results[model] = None
            
            logging.info(f"Successfully analyzed image and extracted JSON content for {model}")
        except Exception as e:
            logging.error(f"Error analyzing image with {model}: {str(e)}")
            results[model] = None

    return results

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        logging.info("POST request received")
        
        if 'file' not in request.files:
            logging.error("No file part in the request")
            return jsonify({'error': 'No file part'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            logging.error("No selected file")
            return jsonify({'error': 'No selected file'}), 400
        
        if file and allowed_file(file.filename):
            logging.info(f"File received: {file.filename}")
            filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            try:
                file.save(filename)
                logging.info(f"File saved: {filename}")
            except Exception as e:
                logging.error(f"Error saving file: {str(e)}")
                return jsonify({'error': 'Error saving file'}), 500
            
            try:
                images, image_paths = pdf_to_images(filename)
                logging.info(f"PDF converted to {len(images)} images")
            except Exception as e:
                logging.error(f"Error processing PDF: {str(e)}")
                if os.path.exists(filename):
                    os.remove(filename)  # Clean up the uploaded file
                return jsonify({'error': str(e)}), 500
            
            all_data = {}
            for idx, (img, img_path) in enumerate(zip(images, image_paths), 1):
                form_type = "form1" if idx == 1 else "form2"
                try:
                    results = analyze_image(img, form_type)
                    if results is not None:
                        all_data[f"form{idx}"] = {
                            "extracted_data": results,
                            "image_url": f"/uploads/{os.path.basename(img_path)}"
                        }
                        logging.info(f"Analyzed form {idx}")
                    else:
                        logging.warning(f"No valid data extracted for form {idx}")
                except Exception as e:
                    logging.error(f"Error analyzing form {idx}: {str(e)}")
            
            # Clean up the original uploaded file
            if os.path.exists(filename):
                os.remove(filename)
                logging.info(f"File removed: {filename}")

            # Compare results and create agreed-upon and differences lists
            agreed_upon = {}
            differences = {}
            total_costs = {model: 0 for model in ["claude-3.5-sonnet", "gpt-4o"]}

            for form_key, form_data in all_data.items():
                claude_data = form_data['extracted_data']['claude-3.5-sonnet']['extracted_data']
                gpt4o_data = form_data['extracted_data']['gpt-4o']['extracted_data']

                agreed_upon[form_key] = {}
                differences[form_key] = {}

                for key in set(claude_data.keys()) | set(gpt4o_data.keys()):
                    if key in claude_data and key in gpt4o_data:
                        if claude_data[key] == gpt4o_data[key]:
                            agreed_upon[form_key][key] = claude_data[key]
                        else:
                            differences[form_key][key] = {
                                'claude': claude_data[key],
                                'gpt4o': gpt4o_data[key]
                            }
                    else:
                        differences[form_key][key] = {
                            'claude': claude_data.get(key, "Not provided"),
                            'gpt4o': gpt4o_data.get(key, "Not provided")
                        }

                # Calculate total costs
                for model in ["claude-3.5-sonnet", "gpt-4o"]:
                    total_costs[model] += form_data['extracted_data'][model]['costs']['total']

            return jsonify({
                'all_data': all_data,
                'agreed_upon': agreed_upon,
                'differences': differences,
                'total_costs': total_costs
            })
        else:
            logging.error("Invalid file type")
            return jsonify({'error': 'Invalid file type'}), 400
    
    return render_template('upload.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(debug=True)
