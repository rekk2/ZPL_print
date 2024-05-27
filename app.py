from flask import Flask, render_template, request, redirect, url_for, make_response, jsonify
import requests
import json
import os
import time

app = Flask(__name__)

# Printer IP address
printer_ip = "192.168.xxx.xxx"

# Path to the JSON file that stores ZPL files
zpl_files_path = "zpl_files.json"

def load_zpl_files():
    if os.path.exists(zpl_files_path):
        with open(zpl_files_path, 'r') as file:
            return json.load(file)
    return {}

def save_zpl_files(zpl_files):
    with open(zpl_files_path, 'w') as file:
        json.dump(zpl_files, file)

@app.route('/')
def index():
    printer_status = check_printer_status()
    zpl_files = load_zpl_files()
    message = request.args.get('message')
    response = make_response(render_template('index.html', printer_status=printer_status, files=zpl_files, message=message))
    response.headers['Cache-Control'] = 'no-store'
    return response

@app.route('/store', methods=['POST'])
def store_zpl():
    filename = request.form['filename']
    zpl_code = request.form['zpl']

    # Remove newline characters before saving
    zpl_code = zpl_code.replace('\r', '').replace('\n', '')

    zpl_files = load_zpl_files()
    zpl_files[filename] = zpl_code
    save_zpl_files(zpl_files)
    
    message = f"File {filename} stored successfully!"
    return jsonify({'message': message})


@app.route('/print', methods=['POST'])
def print_zpl():
    filenames = request.form.getlist('print_filenames')
    message = None

    zpl_files = load_zpl_files()
    combined_zpl_code = ""
    printed_files = []
    for filename in filenames:
        if filename in zpl_files:
            combined_zpl_code += zpl_files[filename] + "\n"  # Concatenate ZPL codes with newline for separation
            printed_files.append(filename)
        else:
            message = f"File {filename} not found."
            return jsonify({'message': message})

    if combined_zpl_code:
        try:
            response = send_zpl_to_printer(combined_zpl_code)
            if response.status_code == 200:
                message = f"Files {', '.join(printed_files)} printed successfully!"
            else:
                message = f"Failed to print files. Status code: {response.status_code}"
        except Exception as e:
            message = f"Failed to print files. Error: {e}"

    return jsonify({'message': message})

def send_zpl_to_printer(zpl_code):
    global printer_ip
    url = f"http://{printer_ip}:9100"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    with requests.Session() as session:
        response = session.post(url, data=zpl_code, headers=headers)
    return response

def check_printer_status():
    response = os.system(f"ping -n 1 {printer_ip}")  # For Windows, use "ping -n 1 {printer_ip}"
    if response == 0:
        return "green"
    else:
        return "red"

if __name__ == '__main__':
    app.run(debug=True)
