# Instalador do SermonCut para Windows: prepara tudo neste computador.
# Vai no zip ao lado de "Instalar SermonCut.bat" e da pasta "sermoncut" com os arquivos do app.
$ErrorActionPreference = "Continue"
$Host.UI.RawUI.WindowTitle = "SermonCut - instalação"
$origem = Join-Path $PSScriptRoot "sermoncut"
$base = Join-Path $env:USERPROFILE "CortesAutomacao"
$sis = Join-Path $base ".sistema"
$local = Join-Path $env:USERPROFILE ".local\bin"

function Passo($t) { Write-Host "`n> $t" -ForegroundColor DarkYellow }
function Ok($t) { Write-Host "  OK  $t" -ForegroundColor Green }
function Erro($t) {
  Write-Host "`nERRO: $t`n" -ForegroundColor Red
  Read-Host "Aperte Enter para fechar"
  exit 1
}

Clear-Host
Write-Host "  SERMONCUT" -ForegroundColor DarkYellow
Write-Host "  Cortes, estudos e conteúdo a partir da pregação`n"
Write-Host "A instalação leva uns 5 minutos. Deixe esta janela aberta até o fim."

Passo "Conferindo o computador"
if (-not (Test-Path $origem)) { Erro "Não achei a pasta 'sermoncut'. Extraia o zip inteiro (botão direito > Extrair tudo) e rode o instalador de dentro da pasta extraída." }
if (-not [Environment]::Is64BitOperatingSystem) { Erro "O SermonCut precisa do Windows 10 ou 11 de 64 bits." }
$livre = [math]::Floor((Get-PSDrive ($env:USERPROFILE.Substring(0, 1))).Free / 1GB)
if ($livre -lt 3) { Erro "O computador precisa de pelo menos 3 GB livres (tem $livre GB)." }
Ok "Windows 64 bits e $livre GB livres"

Passo "Copiando os arquivos do app"
New-Item -ItemType Directory -Force -Path $sis, (Join-Path $base "videos"), (Join-Path $sis "bin") | Out-Null
Get-ChildItem $origem | ForEach-Object {
  # as preferências da pessoa não são apagadas numa reinstalação
  if ($_.Name -eq "ajustes.json" -and (Test-Path (Join-Path $sis "ajustes.json"))) { return }
  Copy-Item $_.FullName $sis -Recurse -Force
}
Ok "Arquivos em $sis"

Passo "Instalando o Python e as ferramentas de vídeo (uns 3 minutos)"
$uv = Join-Path $local "uv.exe"
if (-not (Test-Path $uv)) {
  $env:UV_INSTALL_DIR = $local
  $env:UV_NO_MODIFY_PATH = "1"
  powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex" *> $null
}
if (-not (Test-Path $uv)) { Erro "Não consegui baixar o instalador do Python. Confira a internet." }
& $uv python install 3.12 *> $null
if ($LASTEXITCODE -ne 0) { Erro "Não consegui instalar o Python." }
& $uv venv -q --allow-existing --python 3.12 (Join-Path $sis "venv") *> $null
$py = Join-Path $sis "venv\Scripts\python.exe"
& $uv pip install -q --python $py -r (Join-Path $sis "requisitos.txt")
if ($LASTEXITCODE -ne 0) { Erro "Não consegui instalar as ferramentas. Confira a internet e rode de novo." }
if (-not (Test-Path (Join-Path $sis "ytvenv"))) { cmd /c mklink /J "$sis\ytvenv" "$sis\venv" | Out-Null }
Ok "Python, transcrição, ffmpeg e YouTube prontos"

Passo "Baixando o modelo de transcrição (uns 500 MB, só desta vez)"
& $py -X utf8 -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')" *> $null
if ($LASTEXITCODE -ne 0) { Erro "Não consegui baixar o modelo de transcrição. Confira a internet." }
Ok "Modelo de transcrição pronto"

Passo "Instalando o Claude (opcional, para quem tem assinatura Claude Pro)"
if (-not (Test-Path (Join-Path $local "claude.exe"))) {
  try { powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://claude.ai/install.ps1 | iex" *> $null } catch {}
}
if (Test-Path (Join-Path $local "claude.exe")) { Ok "Claude instalado" } else { Ok "Claude não instalado (dá para usar Gemini, ChatGPT, DeepSeek ou conta grátis)" }

Passo "Criando o atalho SermonCut na Área de Trabalho e no menu Iniciar"
$ws = New-Object -ComObject WScript.Shell
foreach ($pasta in @([Environment]::GetFolderPath("Desktop"), [Environment]::GetFolderPath("Programs"))) {
  $lnk = $ws.CreateShortcut((Join-Path $pasta "SermonCut.lnk"))
  $lnk.TargetPath = Join-Path $sis "venv\Scripts\pythonw.exe"
  $lnk.Arguments = "-X utf8 `"$sis\abrir.py`""
  $lnk.WorkingDirectory = $sis
  $lnk.IconLocation = Join-Path $sis "applet.ico"
  $lnk.Description = "SermonCut - cortes, estudos e conteúdo a partir da pregação"
  $lnk.Save()
}
Ok "Atalho criado"

Write-Host "`nPronto! O SermonCut está na sua Área de Trabalho." -ForegroundColor Green
Write-Host "  Na primeira vez, o app pede para você escolher a IA das análises (tem opções grátis)."
Write-Host "  Depois é só arrastar o vídeo de um culto em cima do atalho, ou trazer pelo Drive ou YouTube.`n"
Start-Process (Join-Path ([Environment]::GetFolderPath("Desktop")) "SermonCut.lnk")
Read-Host "Aperte Enter para fechar esta janela"
