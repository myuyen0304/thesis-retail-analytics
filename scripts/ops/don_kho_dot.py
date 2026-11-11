"""Don kho dot tren Volume sau mot luot nghiem thu: xoa yeu_cau/, lenh/, so_dot/ o thu muc kho Airflow dang dung.

Chay trong container Airflow (co khoa pipeline). Mac dinh chi liet ke; them --thuc-hien moi xoa.
Khong dung toi thu_ket_noi hay thu muc nao khac. Truoc khi xoa phai: tra dashboard, tat hai DAG dot,
xoa ban du lieu cua dot bang don_ban_cu. Chi in duong dan va so file, khong in noi dung.
"""
import argparse
import sys

from scripts.ops import nhap_do

THU_MUC = ('yeu_cau', 'lenh', 'so_dot')
GOC_DUOC_PHEP = '/Volumes/retail_lab/nhap_du_lieu/kho'


def cay(client, thu_muc):
    """Moi file va thu muc con, thu muc con dung sau file cua no."""
    files, dirs = [], []
    for entry in client.files.list_directory_contents(thu_muc):
        path = entry.path.rstrip('/')
        if entry.is_directory:
            sub_files, sub_dirs = cay(client, path)
            files += sub_files
            dirs += sub_dirs + [path]
        else:
            files.append(path)
    return files, dirs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--thuc-hien', action='store_true')
    args = parser.parse_args()
    from databricks.sdk.errors import NotFound

    kho, client = nhap_do._default_store()
    goc = kho.root.rstrip('/')
    if not (goc == GOC_DUOC_PHEP or goc.startswith(GOC_DUOC_PHEP + '/')):
        sys.exit(f'Thu muc kho la ngoai {GOC_DUOC_PHEP}; dung lai.')
    tong = 0
    for ten in THU_MUC:
        root = f'{goc}/{ten}'
        try:
            files, dirs = cay(client, root)
        except NotFound:
            print(f'{root}: khong co')
            continue
        for path in files + dirs:
            if not path.startswith(root + '/'):
                sys.exit(f'Duong dan la ngoai {root}: {path}; dung lai.')
        tong += len(files)
        print(f'{root}: {len(files)} file, {len(dirs)} thu muc con')
        if args.thuc_hien:
            for path in files:
                client.files.delete(path)
            for path in dirs:
                client.files.delete_directory(path)
            client.files.delete_directory(root)
            print(f'  da xoa {root}')
    if not args.thuc_hien:
        print(f'CHI LIET KE ({tong} file). Them --thuc-hien de xoa.')


if __name__ == '__main__':
    main()
