"""
CMFD monthly forcing data download from TPDC FTP — with retry + resume.
Files: temperature, precipitation, wind (monthly, 0.1°, 1979-2018, V0106)
"""
from ftplib import FTP, error_temp, error_perm, error_reply
import os, sys, time, socket

TARGET_DIR = os.path.dirname(os.path.abspath(__file__))

FILES = [
    'temp_CMFD_V0106_B-01_01mo_010deg_197901-201812.nc',
    'prec_CMFD_V0106_B-01_01mo_010deg_197901-201812.nc',
    'wind_CMFD_V0106_B-01_01mo_010deg_197901-201812.nc',
]

FTP_HOST = 'ftp2.tpdc.ac.cn'
FTP_PORT = 6201
FTP_USER = 'download_18259375'
FTP_PASS = '44666332'
FTP_PATH = 'Data_forcing_01mo_010deg'

MAX_RETRIES = 5
BLOCK_SIZE = 512 * 1024  # 512 KB blocks for stability

def connect_ftp():
    ftp = FTP()
    ftp.connect(host=FTP_HOST, port=FTP_PORT, timeout=60)
    ftp.set_pasv(True)
    print(ftp.login(user=FTP_USER, passwd=FTP_PASS), flush=True)
    ftp.cwd(FTP_PATH)
    return ftp

def download_with_retry(ftp_factory, remote_name, local_path):
    """Download with retry on failure, keeping partial file for resume."""
    total = None
    last_retry = 0
    
    for attempt in range(1, MAX_RETRIES + 1):
        last_retry = attempt
        ftp = ftp_factory()
        
        try:
            if total is None:
                total = ftp.size(remote_name)
            
            existing = os.path.getsize(local_path) if os.path.exists(local_path) else 0
            
            if attempt == 1 and existing > 0 and existing < total:
                print(f"  Resuming from {existing/1024/1024:.0f}/{total/1024/1024:.0f} MB", flush=True)
            elif attempt > 1:
                existing = os.path.getsize(local_path) if os.path.exists(local_path) else 0
                print(f"  Retry {attempt}/{MAX_RETRIES}, resuming from {existing/1024/1024:.0f} MB", flush=True)
            
            downloaded = [existing]
            last_update = [time.time()]
            
            # Open file for append (resume)
            mode = 'ab' if existing > 0 else 'wb'
            rest_cmd = f'REST {existing}' if existing > 0 else None
            
            with open(local_path, mode) as f:
                def callback(data):
                    f.write(data)  # 写入文件
                    downloaded[0] += len(data)
                    now = time.time()
                    if now - last_update[0] >= 5:
                        pct = downloaded[0] / total * 100
                        mb = downloaded[0] / 1024 / 1024
                        mb_total = total / 1024 / 1024
                        print(f"  [{remote_name.split('_')[0]}] {pct:.1f}% ({mb:.0f}/{mb_total:.0f} MB)", flush=True)
                        last_update[0] = now
                
                if rest_cmd:
                    ftp.sendcmd(rest_cmd)
                ftp.retrbinary(f'RETR {remote_name}', callback, blocksize=BLOCK_SIZE)
            
            # Verify
            final_size = os.path.getsize(local_path)
            if final_size == total:
                print(f"  ✓ Completed: {remote_name} ({final_size/1024/1024:.0f} MB)", flush=True)
                ftp.quit()
                return True
            else:
                print(f"  ⚠ Size mismatch: {final_size} vs {total}, will retry", flush=True)
                
        except (socket.timeout, TimeoutError, error_temp, error_perm, error_reply, ConnectionResetError, BrokenPipeError, OSError) as e:
            print(f"  ✗ Attempt {attempt}/{MAX_RETRIES} failed: {e}", flush=True)
            time.sleep(5 * attempt)  # Exponential backoff
        finally:
            try:
                ftp.quit()
            except:
                pass
        
        if attempt < MAX_RETRIES:
            time.sleep(3)
    
    print(f"  ✗ FAILED after {last_retry} attempts", flush=True)
    return False

def main():
    print("=" * 60, flush=True)
    print("CMFD Data Download — with retry + resume", flush=True)
    print("=" * 60, flush=True)
    
    os.makedirs(TARGET_DIR, exist_ok=True)
    
    success_count = 0
    fail_count = 0
    
    for i, fname in enumerate(FILES):
        local_path = os.path.join(TARGET_DIR, fname)
        
        # Check if complete
        need_download = True
        if os.path.exists(local_path):
            local_size = os.path.getsize(local_path)
            if local_size > 0:
                try:
                    ftp = connect_ftp()
                    remote_size = ftp.size(fname)
                    ftp.quit()
                    if local_size == remote_size:
                        print(f"\n[{i+1}/3] ✓ SKIP {fname} ({local_size/1024/1024:.0f} MB) — already complete", flush=True)
                        success_count += 1
                        need_download = False
                except:
                    pass
        
        if not need_download:
            continue
        
        # Remove empty/incomplete
        if os.path.exists(local_path) and os.path.getsize(local_path) == 0:
            os.remove(local_path)
        
        print(f"\n[{i+1}/3] ▶ {fname}", flush=True)
        print(f"  Target: {local_path}", flush=True)
        
        start = time.time()
        ftp_factory = connect_ftp  # Fresh connection each time
        
        if download_with_retry(connect_ftp, fname, local_path):
            elapsed = time.time() - start
            speed = os.path.getsize(local_path) / elapsed / 1024 / 1024
            print(f"  Time: {elapsed/60:.1f} min, Speed: {speed:.1f} MB/min", flush=True)
            success_count += 1
        else:
            fail_count += 1
    
    print("\n" + "=" * 60, flush=True)
    print(f"Download finished: {success_count} success, {fail_count} failed", flush=True)
    print("=" * 60, flush=True)
    
    # Verify all
    for fname in FILES:
        local_path = os.path.join(TARGET_DIR, fname)
        if os.path.exists(local_path):
            print(f"  {fname}: {os.path.getsize(local_path)/1024/1024:.0f} MB", flush=True)
        else:
            print(f"  {fname}: NOT FOUND", flush=True)
    
    return 0 if fail_count == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
