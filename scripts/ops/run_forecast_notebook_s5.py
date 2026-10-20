"""PM chạy notebook dự báo B4a từ root; output ở warehouse, không ghi đè notebook của myuyen."""
from pathlib import Path

import nbformat
from nbclient import NotebookClient


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'notebooks/04_forecasting/so_sanh_model.ipynb'
OUTPUT = ROOT / 'warehouse/pipeline-s4/so_sanh_model_s5_chay.ipynb'


def main():
    nb = nbformat.read(SOURCE, as_version=4)
    completed = False
    try:
        NotebookClient(nb, timeout=3600, kernel_name=nb.metadata.kernelspec.name,
                       resources={'metadata': {'path': str(ROOT)}}).execute()
        completed = True
    finally:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        nbformat.write(nb, OUTPUT)
        status = 'Notebook đã chạy xong' if completed else 'Notebook dừng giữa chừng; đã lưu output để xem lỗi'
        print(f'{status}: {OUTPUT}')


if __name__ == '__main__':
    main()
