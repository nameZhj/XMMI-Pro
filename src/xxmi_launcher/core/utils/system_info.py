import logging
import os

from multiprocessing import Process, Array


def is_wine():
    return any(x in os.environ for x in ['WINE', 'WINEPREFIX', 'WINELOADER'])


def log_system_info():
    try:
        process = SystemInfoProcess()
        process.start()
        process.join()
        raw_text = process.data.raw.decode('utf-8', errors='ignore')
        null_idx = raw_text.find('\0')
        if null_idx != -1:
            raw_text = raw_text[:null_idx]
        logging.info(f"System: {raw_text}")
    except Exception as e:
        logging.exception(e)


class SystemInfoProcess(Process):
    def __init__(self):
        Process.__init__(self)
        self.data = Array('c', b'\0' * 512)

    def run(self):
        result = {}

        try:
            wine_suffix = '+WINE' if is_wine() else ''
            result['Platform'] = f"{os.name.upper()}{wine_suffix}"
        except Exception:
            result['Platform'] = 'Unknown'

        try:
            import wmi
            pc = wmi.WMI()
        except Exception as e:
            import traceback
            platform_str = result.get('Platform', 'Unknown')
            error = f"WMI initialization failed on {platform_str} platform: {e}\n\n{traceback.format_exc()}"
            self.data.raw = error.encode('utf-8')
            return

        try:
            os_info = pc.Win32_OperatingSystem()[0]
        except Exception:
            pass

        try:
            os_clean_name = os_info.Name.encode('utf-8').split(b'|')[0].decode('utf-8')
            result['OS'] = f"{os_clean_name} {os_info.Version}"
        except Exception:
            result['OS'] = 'Unknown'

        try:
            result['CPU'] = pc.Win32_Processor()[0].Name.strip()
        except Exception:
            result['CPU'] = 'Unknown'

        try:
            free_ram = round(float(os_info.FreePhysicalMemory) / 1048576, 2)
            total_ram = round(float(os_info.TotalVisibleMemorySize) / 1048576, 2)
            result['RAM'] = f'{free_ram}/{total_ram} GB'
        except Exception:
            result['RAM'] = 'Unknown'

        try:
            gpu_info = []
            for gpu in list(pc.Win32_VideoController()):
                gpu_info.append(gpu.Name.strip())
            result['GPU'] = ', '.join(gpu_info)
        except Exception:
            result['GPU'] = 'Unknown'

        try:
            result['MB'] = pc.Win32_ComputerSystem()[0].model
        except Exception:
            result['MB'] = 'Unknown'

        self.data.raw = str(result).encode('utf-8')
