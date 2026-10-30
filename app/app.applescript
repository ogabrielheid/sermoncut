on run
	abrirInterface()
end run

on open theItems
	repeat with i in theItems
		processar(i)
	end repeat
	abrirInterface()
end open

on processar(f)
	set p to POSIX path of f
	set script_ to (POSIX path of (path to home folder)) & "CortesAutomacao/.sistema/processar.sh"
	do shell script "nohup " & quoted form of script_ & " " & quoted form of p & " > /dev/null 2>&1 &"
end processar

on abrirInterface()
	set script_ to (POSIX path of (path to home folder)) & "CortesAutomacao/.sistema/abrir_interface.sh"
	do shell script quoted form of script_ & " > /dev/null 2>&1"
end abrirInterface
