import webview

w = webview.create_window('Test', html='<body>test</body>', transparent=True)
def on_load():
    print(dir(w.native))
    w.destroy()
    
webview.start(on_load)
