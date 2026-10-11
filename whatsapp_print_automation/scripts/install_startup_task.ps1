param(
    [string]$TaskName = "WhatsAppPrinterAutomation",
    [string]$ProjectDir = (Resolve-Path "$PSScriptRoot\..").Path
)

$PythonExe = Join-Path $ProjectDir ".venv\Scripts\python.exe"
$MainPy = Join-Path $ProjectDir "main.py"

if (-not (Test-Path $PythonExe)) {
    throw "No se encontro Python virtual en $PythonExe. Crea el entorno primero."
}

if (-not (Test-Path $MainPy)) {
    throw "No se encontro main.py en $MainPy."
}

$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$MainPy`"" -WorkingDirectory $ProjectDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Automatizacion de descarga e impresion desde WhatsApp Web" -Force

Write-Host "Tarea instalada: $TaskName"
