from io import BytesIO

from flask import jsonify, request, send_file


def json_response(payload, status_code=200):
    response = jsonify(payload)
    response.status_code = status_code
    return response


def json_error(code, message, status_code):
    return json_response({"error": code, "message": message}, status_code)


def read_json_body():
    return request.get_json(silent=True) or {}


def send_download(content, filename, mimetype):
    kwargs = {"mimetype": mimetype, "as_attachment": True}
    payload = BytesIO(content) if isinstance(content, (bytes, bytearray)) else content
    try:
        return send_file(payload, download_name=filename, **kwargs)
    except TypeError:
        return send_file(payload, attachment_filename=filename, **kwargs)
