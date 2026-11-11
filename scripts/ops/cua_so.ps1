# Cua so bao tri (thiet ke 11): dua code main len web public va Airflow production, dung lai ban du lieu.
# PM chay tung buoc trong PowerShell rieng, ngoai Claude Code. Chi dung ASCII vi PowerShell 5.1 doc sai UTF-8 khong BOM.
# Thu tu: truoc -> web -> dung -> quota -> chay -> kiem -> cong_bo -> (hom sau) sau.
# Hong giua chung: quay_lai <ban_cu> (Airflow) va quay_lai_web (web public).
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('truoc', 'web', 'dung', 'quota', 'chay', 'kiem', 'cong_bo', 'sau', 'quay_lai', 'quay_lai_web', 'bat_dot')]
    [string]$Buoc,
    [Parameter(Position = 1)]
    [string]$Them
)
$ErrorActionPreference = 'Stop'
# Commit main da qua app thu ngay 2026-11-11 (PR #35). main doi thi phai thu app lai, khong sua so nay cho qua.
$Commit = '213e8fbd193653b1c39475f8c29ad12371fe6fea'
$Main = 'D:\retail-analytics'
$Luu = 'D:\retail-analytics\warehouse\cua_so'
$ComposeMoi = Join-Path $Luu 'docker-compose.airflow.yml'
$ComposeCu = Join-Path $Main 'docker-compose.airflow.yml'
$Project = 'retail-analytics'
$Scheduler = 'retail-analytics-airflow-scheduler-1'
$ImageCu = 'retail-airflow:truoc-r2'
$TagWeb = 'truoc-cua-so-r2'
$Root = 'warehouse/pipeline/docker'
$RunFile = Join-Path $Luu 'run_id.txt'

function Chay {
    param([string]$Exe, [string[]]$Thamso)
    & $Exe @Thamso
    if ($LASTEXITCODE -ne 0) { throw "Lenh loi, exit=$LASTEXITCODE`: $Exe $($Thamso -join ' ')" }
}

function TrongAirflow {
    param([string[]]$Lenh)
    Chay 'docker' (@('exec', '-w', '/opt/retail', $Scheduler) + $Lenh)
}

function LenhPipeline {
    param([string[]]$Lenh)
    TrongAirflow (@('/opt/pipeline/bin/python', '-m', 'scripts.pipeline.cli') + $Lenh)
}

function Compose {
    param([string]$File, [string[]]$Lenh)
    # Giu dung project cua Airflow dang chay; khong dung --remove-orphans vi retail_dwh cung project.
    Chay 'docker' (@('compose', '-p', $Project, '--project-directory', $Main, '-f', $File) + $Lenh)
}

function RunId {
    if (-not (Test-Path $RunFile)) { throw 'Chua co run_id; chay buoc chay truoc' }
    $id = (Get-Content -LiteralPath $RunFile -Raw).Trim()
    if ($id -notmatch '^[a-f0-9]{24}$') { throw "run_id hong: $RunFile" }
    return $id
}

function ConTro {
    # Doc con tro tren cloud bang code trong image (chi doc, khong in khoa).
    $py = 'from scripts.pipeline.runtime import Databricks; from scripts.pipeline.state import Registry; ' +
          'c = Databricks(); p = Registry(''warehouse/pipeline/docker'', c.query).read()[''payload'']; c.close(); ' +
          'print(''active   :'', p[''active'']); print(''rollback :'', (p.get(''dich_rollback'') or {}).get(''release_id'')); print(''dashboard:'', p.get(''dashboard''))'
    TrongAirflow @('/opt/pipeline/bin/python', '-c', $py)
}

function ImageId {
    param([string]$Ten)
    # Qua cmd de PowerShell 5.1 khong bien stderr cua docker thanh loi khi image chua co.
    $id = cmd /c "docker image inspect -f {{.Id}} $Ten 2>nul"
    if ($LASTEXITCODE -ne 0) { return $null }
    return ($id | Select-Object -First 1).Trim()
}

switch ($Buoc) {
    'truoc' {
        # Chi doc. Dung khi bat ky dong nao bao loi.
        Chay 'git' @('-C', $Main, 'fetch', '-q', 'origin')
        $origin = (& git -C $Main rev-parse origin/main).Trim()
        if ($origin -ne $Commit) { throw "origin/main ($origin) khac commit da thu app ($Commit). Bao Claude." }
        & git -C $Main merge-base --is-ancestor origin/app/myuyen $Commit
        if ($LASTEXITCODE -ne 0) { throw 'app/myuyen khong nam trong main; khong day thang duoc. Bao Claude.' }
        Chay 'docker' @('ps', '--format', '{{.Names}} | {{.Image}} | {{.Status}}')
        if (ImageId $ImageCu) { throw "Da co image $ImageCu tu lan truoc; bao Claude truoc khi ghi de." }
        Write-Output 'Lich su 5 lan chay gan nhat (lan 08:00 hom nay phai xong, khong con dang chay):'
        LenhPipeline @('history', '--target', 'databricks', '--root', $Root, '--limit', '5')
        Write-Output "DAT: main = $Commit, app/myuyen day thang duoc. Nho dat Sleep = Never va cam sac."
    }
    'web' {
        # Buoc 1 thiet ke 11: gan tag duong lui roi dua code main len nhanh web public.
        Chay 'git' @('-C', $Main, 'fetch', '-q', 'origin')
        $cu = (& git -C $Main rev-parse origin/app/myuyen).Trim()
        Chay 'git' @('-C', $Main, 'tag', $TagWeb, $cu)
        Chay 'git' @('-C', $Main, 'push', 'origin', $TagWeb)
        Chay 'git' @('-C', $Main, 'push', 'origin', "$($Commit):refs/heads/app/myuyen")
        Write-Output "Da gan tag $TagWeb = $cu va day $Commit len app/myuyen."
        Write-Output 'Gio Reboot web public, kiem: ban dbb80f56 (refresh 02/11), PS1 2012-2022 G 16,43 ty R 12,52 ty, mot cau chat.'
    }
    'dung' {
        # Buoc 2-4: giu image cu, tam dung DAG, dung image tu git archive cua dung commit, dung lai container.
        $cu = ImageId $ImageCu
        $hien = ImageId 'retail-airflow:local'
        if (-not $cu) {
            Chay 'docker' @('tag', 'retail-airflow:local', $ImageCu)
        } elseif ($cu -ne $hien) {
            # Lan truoc da dung xong image moi; khong ghi de duong lui bang image moi.
            throw "$ImageCu da co va khac retail-airflow:local. Bao Claude."
        }
        TrongAirflow @('airflow', 'dags', 'pause', '-y', 'retail_batch_pipeline')
        if (-not (Test-Path $Luu)) { New-Item -ItemType Directory $Luu | Out-Null }
        $tam = Join-Path $env:TEMP ('retail_cua_so_' + $Commit.Substring(0, 8))
        if (Test-Path $tam) { throw "Thu muc tam da co, xem lai roi xoa: $tam" }
        New-Item -ItemType Directory $tam | Out-Null
        $tar = Join-Path $tam 'code.tar'
        Chay 'git' @('-c', 'core.autocrlf=false', '-C', $Main, 'archive', '--format=tar', '-o', $tar, $Commit)
        Chay 'tar' @('-xf', $tar, '-C', $tam)
        Remove-Item -LiteralPath $tar
        Copy-Item -LiteralPath (Join-Path $tam 'docker-compose.airflow.yml') -Destination $ComposeMoi -Force
        Chay 'docker' @('build', '-f', (Join-Path $tam 'deploy\airflow\Dockerfile'), '-t', 'retail-airflow:local', '--label', "commit=$Commit", $tam)
        Remove-Item -Recurse -Force -LiteralPath $tam
        # Compose cua main: them pool retail_writer va mount data_demo. Worktree chinh dang o nhanh khac nen dung ban sao.
        Compose $ComposeMoi @('up', '-d', '--no-build', 'airflow-api', 'airflow-scheduler', 'airflow-dag-processor')
        Start-Sleep -Seconds 90
        $nhan = (& docker inspect -f '{{json .Config.Labels}}' $Scheduler)
        Write-Output "Container dang chay image commit: $nhan"
        TrongAirflow @('airflow', 'pools', 'get', 'retail_writer')
        TrongAirflow @('/opt/pipeline/bin/python', '-c', 'import scripts.ops.nhap_do, scripts.ops.don_ban_cu; print(''import dat'')')
        TrongAirflow @('airflow', 'dags', 'list')
        Write-Output "Kiem: commit = $Commit; ba DAG retail_batch_pipeline, nhap_du_lieu_do, retail_dot_pipeline deu is_paused = True."
        Write-Output 'Chua thay du ba DAG thi doi 1 phut roi chay: docker exec retail-analytics-airflow-scheduler-1 airflow dags list'
    }
    'quota' {
        # Can it nhat 183 cho (100 lan dung nay + 83 du phong). Bao cao don chi doc.
        ConTro
        TrongAirflow @('/opt/pipeline/bin/python', '-m', 'scripts.ops.don_ban_cu', '--catalog', 'retail_lab')
        Write-Output 'DAT khi: quota da dung + 183 <= 500 (hoac tong bang catalog + 183 <= 500 neu khong doc duoc quota). Ghi lai ma active o tren.'
    }
    'chay' {
        # Buoc 5: chay tay tung stage, KHONG trigger DAG (DAG tu publish). Chay lai buoc nay se tiep tu stage chi dinh.
        if (-not (Test-Path $Luu)) { New-Item -ItemType Directory $Luu | Out-Null }
        if (-not (Test-Path $RunFile)) {
            ([guid]::NewGuid().ToString('N')).Substring(0, 24) | Set-Content -LiteralPath $RunFile -Encoding ascii
        }
        $id = RunId
        $ext = (& docker exec $Scheduler printenv RETAIL_PIPELINE_DEFAULT_EXTENSIONS)
        $mo = @()
        if ($ext) { foreach ($t in ($ext -split ',')) { if ($t.Trim()) { $mo += @('--extension', $t.Trim()) } } }
        $stages = @('prepare', 'forecast', 'build', 'validate')
        $tu = if ($Them) { [array]::IndexOf($stages, $Them) } else { 0 }
        if ($tu -lt 0) { throw 'Them phai la prepare, forecast, build hoac validate' }
        Write-Output "run_id = $id; phan mo rong = $ext"
        foreach ($s in $stages[$tu..($stages.Count - 1)]) {
            Write-Output "=== $s bat dau $(Get-Date -Format HH:mm:ss) ==="
            $lenh = @($s, '--run-id', $id, '--target', 'databricks', '--root', $Root)
            if ($s -eq 'prepare') { $lenh += $mo }
            LenhPipeline $lenh
        }
        Write-Output 'Xong 4 stage. Chay buoc kiem.'
    }
    'kiem' {
        # Buoc 6: validate da so G/COGS theo ngay; xem lich su va con tro truoc khi cong bo.
        $id = RunId
        LenhPipeline @('history', '--target', 'databricks', '--root', $Root, '--limit', '6')
        ConTro
        Write-Output "run_id = $id. DAT khi 4 dong cua run_id nay deu dat, validate dat, active van la ban cu."
    }
    'cong_bo' {
        # Buoc 7: cong bo roi bat lai lich 08:00.
        $id = RunId
        LenhPipeline @('publish', '--run-id', $id, '--target', 'databricks', '--root', $Root)
        ConTro
        TrongAirflow @('airflow', 'dags', 'unpause', '-y', 'retail_batch_pipeline')
        Write-Output 'Da cong bo va bat lai retail_batch_pipeline. Kiem web: refresh hom nay, PS1 2012-2022 G 16,43 ty, chat 1 cau doanh thu + 1 cau du bao.'
    }
    'sau' {
        # Hom sau, sau 08:00: lan chay lich phai ra bo_qua (cung code, cung du lieu).
        LenhPipeline @('history', '--target', 'databricks', '--root', $Root, '--limit', '6')
        ConTro
    }
    'quay_lai' {
        # Tra con tro va image cu. Chi tra con tro thi 08:00 se dung lai ban moi vi code_version lech.
        if ($Them -notmatch '^[a-f0-9]{24}$') { throw 'Can ma ban cu 24 ky tu hex (dong active o buoc quota)' }
        TrongAirflow @('airflow', 'dags', 'pause', '-y', 'retail_batch_pipeline')
        LenhPipeline @('rollback', '--run-id', ([guid]::NewGuid().ToString('N')).Substring(0, 24), '--release-id', $Them, '--target', 'databricks', '--root', $Root)
        Chay 'docker' @('tag', $ImageCu, 'retail-airflow:local')
        Compose $ComposeCu @('up', '-d', '--no-build', 'airflow-api', 'airflow-scheduler', 'airflow-dag-processor')
        Write-Output 'Da tra con tro va image cu; retail_batch_pipeline DANG TAM DUNG. Bao Claude truoc khi bat lai.'
    }
    'quay_lai_web' {
        Chay 'git' @('-C', $Main, 'push', '--force', 'origin', "refs/tags/$($TagWeb):refs/heads/app/myuyen")
        Write-Output "Da tra app/myuyen ve $TagWeb. Reboot web public."
    }
    'bat_dot' {
        # Chi lam o Moc 1 (khoang 11-24), sau khi them khoa RETAIL_NHAP_* cho web public.
        foreach ($dag in 'retail_dot_pipeline', 'nhap_du_lieu_do') {
            TrongAirflow @('airflow', 'dags', 'unpause', '-y', $dag)
        }
        TrongAirflow @('airflow', 'dags', 'list')
    }
}
