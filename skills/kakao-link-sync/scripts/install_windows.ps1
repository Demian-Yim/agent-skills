# install_windows.ps1 — 데미안 자산 폴더(D:\00 Antigravity\00 Skills)와 Claude 스킬 폴더에 설치
$Src = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Targets = @("D:\00 Antigravity\00 Skills\kakao-link-sync", "$env:USERPROFILE\.claude\skills\kakao-link-sync")
foreach ($t in $Targets) {
  New-Item -ItemType Directory -Force -Path $t | Out-Null
  Copy-Item -Path "$Src\*" -Destination $t -Recurse -Force
  Write-Host "설치: $t"
}
pip install pywin32 | Out-Null
Write-Host "다음: python `"$($Targets[0])\scripts\kakao_pull_windows.py`" --list"
