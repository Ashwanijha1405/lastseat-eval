# PowerShell front end; same commands as the Makefile, for Windows without make.
# Everything still runs inside Docker.
#
#   .\run.ps1 help
#   .\run.ps1 free-models
#   .\run.ps1 pilot                     # free set (default): prints the plan only
#   .\run.ps1 pilot -Yes                # start it
#   .\run.ps1 run -Config paid -Yes -Run 20261108T2000Z -Jobs 2
#
# If scripts are blocked: powershell -ExecutionPolicy Bypass -File .\run.ps1 <command> ...
param(
    [Parameter(Position = 0)][string]$Command = "help",
    [string]$Config = "free",
    [switch]$Yes,
    [switch]$New,
    [string]$Run,
    [string]$From,
    [int]$Jobs = 0,
    [string[]]$Task,
    [string[]]$Model,
    [switch]$Regrade,
    [int]$Trials = 3,
    [string]$Effort = "high",
    [ValidateSet("claude", "antigravity")][string]$Cli = "claude"
)
# No $ErrorActionPreference = "Stop": in Windows PowerShell 5.1 it turns docker's
# ordinary stderr progress lines into fatal errors. Exit codes are checked instead.
Set-Location $PSScriptRoot

function Invoke-Checked([string[]]$Cmd) {
    & $Cmd[0] $Cmd[1..($Cmd.Length - 1)]
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

function Start-Db { Invoke-Checked @("docker", "compose", "up", "-d", "--wait", "db") }

function Invoke-Eval([string[]]$Rest) {
    Invoke-Checked (@("docker", "compose", "run", "--rm", "eval") + $Rest)
}

function Get-RunnerArgs([int]$Trials) {
    $a = @("python", "-m", "lastseat.runner", "run", "--trials", "$Trials", "--config", $Config)
    if ($Yes) { $a += "--yes" }
    if ($New) { $a += "--new" }
    if ($Run) { $a += @("--run-id", $Run) }
    if ($From) { $a += @("--estimate-from", $From) }
    if ($Jobs -gt 0) { $a += @("--jobs", "$Jobs") }
    foreach ($t in $Task) { $a += @("--task", $t) }
    foreach ($m in $Model) { $a += @("--model", $m) }
    return , $a
}

switch ($Command) {
    "help" {
        @(
            ".\run.ps1 up | down | build | test | psql | shell",
            ".\run.ps1 validate [-Task t01_flash_sale]   references pass, wrong variants fail",
            ".\run.ps1 models [-Config paid]             live IDs and prices of a model set",
            ".\run.ps1 free-models                       every zero-priced :free model",
            ".\run.ps1 quota                             free-model requests used / left today",
            ".\run.ps1 summary -Run <run_id> [-Regrade]   write results/<run_id>/summary.md (-Regrade: no API)",
            ".\run.ps1 dry-run                           mock model returning the references, no API",
            ".\run.ps1 official-cli -Model claude-opus-5-5 (-New | -Run <id>) [-Task ..] [-Trials 3] [-Yes]",
            "                                            Claude Code headless (claude -p), one call at a time",
            "  official-cli -Cli antigravity -Model gemini-3.8-flash-high ...  Gemini via Antigravity CLI (agy --print)",
            ".\run.ps1 pilot [-Yes]                      1 trial per model and task",
            ".\run.ps1 run [-Yes]                        5 trials",
            "  run/pilot options: -Config free|paid (default free) -Run <id> -New -From <pilot id>",
            "                     -Jobs <n> -Task <id>[,<id>] -Model <slug>[,<slug>]",
            "  A pilot/run resumes only an unfinished run with the same tasks, models and trials;",
            "  anything else is refused: -Run <id> continues a named run, -New starts a fresh one."
        ) | ForEach-Object { Write-Output $_ }
    }
    "up" { Start-Db }
    "down" { Invoke-Checked @("docker", "compose", "down") }
    "build" { Invoke-Checked @("docker", "compose", "build", "eval") }
    "test" { Start-Db; Invoke-Eval @("python", "-m", "pytest") }
    "validate" {
        Start-Db
        $a = @("python", "-m", "lastseat.validate")
        foreach ($t in $Task) { $a += @("--task", $t) }
        Invoke-Eval $a
    }
    "models" { Invoke-Eval @("python", "-m", "lastseat.runner", "models", "--config", $Config) }
    "free-models" { Invoke-Eval @("python", "-m", "lastseat.runner", "models", "--list-free") }
    "quota" { Invoke-Eval @("python", "-m", "lastseat.runner", "quota", "--config", $Config) }
    "summary" {
        if (-not $Run) { Write-Output "summary needs -Run <run_id>"; exit 2 }
        Start-Db
        $a = @("python", "-m", "lastseat.summary", "results/$Run")
        if ($Regrade) { $a += "--regrade" }
        Invoke-Eval $a
    }
    "official-cli" {
        # Claude Code headless (claude -p) on this machine; prepare and grade run in Docker.
        if ($Model.Count -ne 1) { Write-Output "official-cli needs exactly one -Model <full model name>"; exit 2 }
        if ($New -and -not $Run) { $Run = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ") + "-cli" }
        if (-not $Run) { Write-Output "official-cli needs -Run <id> (continue) or -New (start); never implicit"; exit 2 }
        Start-Db
        $a = @("python", "-m", "lastseat.official_cli", "prepare", "--run-id", $Run, "--model", $Model[0],
               "--trials", "$Trials", "--effort", $Effort, "--cli", $Cli)
        foreach ($t in $Task) { $a += @("--task", $t) }
        Invoke-Eval $a
        if (-not $Yes) { Write-Output "prepared only; add -Yes -Run $Run to ask the CLI"; exit 0 }
        & python lastseat/cli_host.py "results/$Run"
        $askExit = $LASTEXITCODE
        Invoke-Eval @("python", "-m", "lastseat.official_cli", "grade", "results/$Run")
        Invoke-Eval @("python", "-m", "lastseat.summary", "results/$Run")
        exit $askExit
    }
    "dry-run" { Start-Db; Invoke-Eval ((Get-RunnerArgs 1) + "--dry-run") }
    "pilot" { Start-Db; Invoke-Eval (Get-RunnerArgs 1) }
    "run" { Start-Db; Invoke-Eval (Get-RunnerArgs 5) }
    "psql" { Start-Db; Invoke-Checked @("docker", "compose", "exec", "db", "psql", "-U", "lastseat", "-d", "lastseat") }
    "shell" { Start-Db; Invoke-Eval @("bash") }
    default { Write-Output "unknown command '$Command'; try .\run.ps1 help"; exit 2 }
}
