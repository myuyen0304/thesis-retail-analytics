# Tong duyet dot 2023 tu giao dien (thiet ke 11). PM chay tung buoc trong PowerShell rieng.
# File nay chi dung ASCII vi PowerShell 5.1 doc sai UTF-8 khong BOM.
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('dung', 'truoc', 'bat', 'trang_thai', 'tat_do', 'kiem', 'kiem_t2', 'bao_cao_don', 'xoa_ban', 'xoa_kho', 'ha')]
    [string]$Buoc,
    [Parameter(Position = 1)]
    [string]$Ban
)
$ErrorActionPreference = 'Stop'
$Repo = 'D:\retail-analytics-nap'
$Compose = Join-Path $Repo 'scripts\ops\tong_duyet.compose.yml'
$Image = 'retail-airflow:thu-l2'
$BatchDag = 'deploy/airflow/dags/retail_batch_pipeline.py'

function Chay {
    param([string]$Exe, [string[]]$Thamso)
    & $Exe @Thamso
    if ($LASTEXITCODE -ne 0) { throw "Lenh loi, exit=$LASTEXITCODE`: $Exe $($Thamso -join ' ')" }
}

function TrongContainer {
    param([string[]]$Lenh)
    Chay 'docker' (@('compose', '-f', $Compose, 'exec', '-T', '-w', '/opt/retail', 'airflow-scheduler') + $Lenh)
}

function Kiem {
    param([string]$Giai_doan)
    TrongContainer @('/opt/pipeline/bin/python', '-m', 'scripts.ops.tong_duyet_kiem', $Giai_doan)
}

function Don {
    param([string[]]$Them)
    TrongContainer (@('/opt/pipeline/bin/python', '-m', 'scripts.ops.don_ban_cu', '--catalog', 'retail_lab') + $Them)
}

switch ($Buoc) {
    'dung' {
        $commit = (& git -C $Repo rev-parse HEAD).Trim()
        if ($LASTEXITCODE -ne 0) { throw 'Khong doc duoc commit' }
        $tam = Join-Path $env:TEMP ('retail_thu_' + $commit.Substring(0, 8))
        if (Test-Path $tam) { throw "Thu muc tam da co, xem lai roi xoa: $tam" }
        New-Item -ItemType Directory $tam | Out-Null
        $tar = Join-Path $tam 'code.tar'
        Chay 'git' @('-c', 'core.autocrlf=false', '-C', $Repo, 'archive', '--format=tar', '-o', $tar, $commit)
        Chay 'tar' @('-xf', $tar, '-C', $tam)
        Remove-Item -LiteralPath $tar
        # Bo DAG tu publish khoi image thu: bo thu khong the cong bo nham.
        Remove-Item -LiteralPath (Join-Path $tam $BatchDag)
        Chay 'docker' @('build', '-f', (Join-Path $tam 'deploy\airflow\Dockerfile'), '-t', $Image, '--label', "commit=$commit", $tam)
        Remove-Item -Recurse -Force -LiteralPath $tam
        Chay 'docker' @('compose', '-f', $Compose, 'up', '-d', '--wait', 'airflow-db')
        Chay 'docker' @('compose', '-f', $Compose, 'up', '-d', 'airflow-api', 'airflow-scheduler', 'airflow-dag-processor')
        Write-Output "Da dung bo thu tu commit $commit. Airflow thu: http://localhost:8081"
    }
    'truoc' { Kiem 'truoc' }
    'bat' {
        foreach ($dag in 'retail_dot_pipeline', 'nhap_du_lieu_do') {
            TrongContainer @('airflow', 'dags', 'unpause', '-y', $dag)
        }
        TrongContainer @('airflow', 'dags', 'list')
    }
    'trang_thai' { Kiem 'trang_thai' }
    'tat_do' { TrongContainer @('airflow', 'dags', 'pause', '-y', 'nhap_du_lieu_do') }
    'kiem' { Kiem 'kiem' }
    'kiem_t2' { Kiem 'kiem_t2' }
    'bao_cao_don' { Don @() }
    'xoa_ban' {
        if ($Ban -notmatch '^[a-f0-9]{24}$') { throw 'Can ma ban 24 ky tu hex' }
        Don @('--xoa', $Ban, '--thuc-hien')
    }
    'xoa_kho' { Kiem 'xoa_kho' }
    'ha' {
        Chay 'docker' @('compose', '-f', $Compose, 'down', '-v')
        Chay 'docker' @('image', 'rm', $Image)
    }
}
