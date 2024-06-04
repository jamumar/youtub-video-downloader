import os
import re
import threading
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import yt_dlp
import eventlet
eventlet.monkey_patch()

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

def strip_ansi_escape_sequences(text):
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    return ansi_escape.sub('', text)

def download_video(url, resolution, socketio):
    def progress_hook(d):
        if d['status'] == 'downloading':
            percent_str = strip_ansi_escape_sequences(d['_percent_str'])
            try:
                percent = float(percent_str.strip().replace('%', ''))
                socketio.emit('progress', {'percent': percent})
            except ValueError:
                socketio.emit('error', {'message': 'Failed to parse progress percentage.'})
        elif d['status'] == 'finished':
            socketio.emit('progress', {'percent': 100})
            socketio.emit('status', {'message': 'Download completed!'})

    ydl_opts = {
        'format': resolution,
        'progress_hooks': [progress_hook],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError as e:
        socketio.emit('error', {'message': str(e)})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_info', methods=['POST'])
def video_info():
    url = request.json['url']
    ydl_opts = {'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        thumbnail = info.get('thumbnail')
        title = info.get('title')
        formats = [
            {'format_id': f['format_id'], 'format_note': f['format_note'], 'ext': f['ext']}
            for f in info['formats'] if f.get('vcodec') != 'none'
        ]
        return jsonify({'thumbnail': thumbnail, 'title': title, 'formats': formats})

@socketio.on('download')
def handle_download(data):
    video_url = data['url']
    resolution = data['resolution']
    thread = threading.Thread(target=download_video, args=(video_url, resolution, socketio))
    thread.start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)
