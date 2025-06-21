# config: utf-8
import hashlib
from pathlib import Path
from urllib import request
from urllib.error import HTTPError

import pytest


@pytest.fixture(scope='session', autouse=True)
def prepare_prefetch():
    # setup
    ## download prefetch sample
    base_url = 'https://raw.githubusercontent.com/EricZimmerman/Prefetch/master/Prefetch.Test/TestFiles/Win10'
    files = [
        { 'name': 'CALC.EXE-3FBEF7FD.pf', 'md5': '40b8917687c2b1cf8ac5bfeea6476a39', }, 
        { 'name': 'CALCULATOR.EXE-6940BD5C.pf', 'md5': '00303143c458d2479d33511bc3b9610e', },
        { 'name': 'CHROME.EXE-B3BA7868.pf', 'md5': '221eacbee606746ecda2ee8ce0f187d0', },
        { 'name': 'CMD.EXE-D269B812.pf', 'md5': '3f665f2441f1bfa535fd4c4746a9d975', },
        { 'name': 'DCODEDCODEDCODEDCODEDCODEDCOD-E65B9FE8.pf', 'md5': 'a3691e9b4578fe5461e75b760ae90932', },
        { 'name': 'DEVENV.EXE-854D7862.pf', 'md5': '4aeb838bfb7a8937f1c3cd7d74835792', }
    ]
    
    cachedir = Path(__file__).parent / Path('cache')
    cachedir.mkdir(exist_ok=True)
    
    for file in files:
        cache_file = cachedir / file["name"]
        
        # Skip download if file already exists and has correct MD5
        if cache_file.exists():
            existing_md5 = hashlib.md5(cache_file.read_bytes()).hexdigest()
            if existing_md5 == file["md5"]:
                continue
        
        # Download file
        file_url = f'{base_url}/{file["name"]}'
        try:
            data = request.urlopen(file_url).read()
            with open(cache_file, mode="wb") as f:
                f.write(data)

            # Verify MD5
            pf_md5 = hashlib.md5(cache_file.read_bytes()).hexdigest()
            assert pf_md5 == file["md5"], f"MD5 mismatch for {file['name']}: expected {file['md5']}, got {pf_md5}"
            
        except HTTPError as e:
            pytest.skip(f"Could not download test file {file['name']}: {e}")
        except Exception as e:
            pytest.skip(f"Error processing test file {file['name']}: {e}")

    # transition to test cases
    yield

    # teardown
    ## remove cache files
    cachedir = Path(__file__).parent / Path('cache')
    for file in cachedir.glob('**/*[!.gitkeep]'):
        if file.is_file():
            file.unlink()