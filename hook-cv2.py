from PyInstaller.utils.hooks import collect_all

def hook(hook_api):
    # Collect all OpenCV binaries, data files, and hidden imports
    datas, binaries, hiddenimports = collect_all('cv2')
    hook_api.add_datas(datas)
    hook_api.add_binaries(binaries)
    hook_api.add_imports(*hiddenimports)