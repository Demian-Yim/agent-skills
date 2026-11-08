# register_windows_task.ps1 — Windows 작업 스케줄러에 '카톡 링크 자동 동기화' 등록 (매일 2회)
# 관리자 PowerShell 에서:  powershell -ExecutionPolicy Bypass -File .\register_windows_task.ps1
# 전제: 로그온 상태 + PC 카톡 로그인 + '나와의 채팅' 창이 열려 있어야 수집됨 (최소화 금지)
$Dir   = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)   # 스크립트 상위 폴더
$Py    = (Get-Command python).Source
$Room  = Read-Host "나와의 채팅 창 제목 (= 내 카톡 이름, 예: Demian 임정훈)"
$Token = Read-Host "Notion 통합 토큰 (secret_... / ntn_...)"
[Environment]::SetEnvironmentVariable("KAKAO_ROOM",  $Room,  "User")
[Environment]::SetEnvironmentVariable("NOTION_TOKEN", $Token, "User")

$Action  = New-ScheduledTaskAction -Execute $Py -Argument "kakao_sync.py --source windows --pageup 10 --titles" -WorkingDirectory $Dir
$Trig1   = New-ScheduledTaskTrigger -Daily -At 09:00
$Trig2   = New-ScheduledTaskTrigger -Daily -At 21:00
$Setting = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName "KakaoLinkSync" -Action $Action -Trigger $Trig1,$Trig2 -Settings $Setting -RunLevel Limited -Force
Write-Host "등록 완료. 즉시 테스트: Start-ScheduledTask -TaskName KakaoLinkSync ; 로그: $Dir\kakao_sync.log"
