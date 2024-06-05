import os
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import yt_dlp
import threading
import re
from pathlib import Path

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

def strip_ansi_escape_sequences(text):
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    return ansi_escape.sub('', text)

def download_video(url, resolution, output_path, socketio=None):
    def progress_hook(d):
        if d['status'] == 'downloading':
            percent_str = strip_ansi_escape_sequences(d['_percent_str'])
            try:
                percent = float(percent_str.strip().replace('%', ''))
                socketio.emit('progress', {'percent': percent})
            except ValueError:
                print(f"Failed to parse percent: {percent_str}")
        elif d['status'] == 'finished':
            socketio.emit('progress', {'percent': 100})
            socketio.emit('status', {'message': 'Download completed!'})

    ydl_opts = {
        'format': str(resolution),
        'outtmpl': f'{output_path}/%(title)s.%(ext)s',
        'progress_hooks': [progress_hook],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            # Get the file path of the downloaded video
            info = ydl.extract_info(url, download=False)
            video_file = ydl.prepare_filename(info)
            socketio.emit('download_link', {'link': video_file})
    except yt_dlp.utils.DownloadError as e:
        socketio.emit('error', {'message': str(e)})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_info', methods=['POST'])
def video_info():
    url = request.json['url']
    ydl_opts = {'quiet': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            thumbnail = info.get('thumbnail')
            title = info.get('title')
            formats = [
                {'format_id': f['format_id'], 'format_note': f['format_note'] or f['height'], 'ext': f['ext']}
                for f in info['formats'] if f.get('vcodec') != 'none' and f.get('acodec') != 'none'
            ]
            return jsonify({'thumbnail': thumbnail, 'title': title, 'formats': formats})
    except yt_dlp.utils.DownloadError as e:
        return jsonify({'error': str(e)})

@socketio.on('download')
def handle_download(data):
    url = data['url']
    resolution = data['resolution']
    output_path = str(Path.home() / "Downloads")
    download_thread = threading.Thread(target=download_video, args=(url, resolution, output_path, socketio))
    download_thread.start()

if __name__ == '__main__':
    socketio.run(app, debug=True)
