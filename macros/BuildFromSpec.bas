Attribute VB_Name = "BuildFromSpec"
' ============================================================================
' BuildFromSpec - SolidWorks 2017 VBA macro
'
' Reads a text spec (see README.md, examples/*.txt) and builds:
'   * every PART as a separate .SLDPRT with a feature tree:
'       Front Plane -> "Profile" sketch -> "Body" (Revolve 360)
'       -> "HolesN" (Cut-Extrude on an offset plane, circular hole pattern)
'       -> "AXIS" (axis of rotation = X) -> "PORT_<name>" planes (interfaces)
'   * if ASSEMBLY is given - an .SLDASM with all parts:
'       MOTION fixed (default) - 3 coincident mates to the assembly planes;
'       MOTION rotate          - axis on the AXIS of the first fixed part +
'                                Right plane on Right plane: free rotation about X.
'   * DATA key=value lines -> custom properties of the assembly,
'     PORT lines -> "PORT_<name>" plane + custom property of the part,
'     MASS <kg> -> part density set so that the part has exactly this mass,
'     FLATS  -> "FlatsN" (milled flats, e.g. a square flange cut from a turned disc),
'     KEYWAY -> "KeywayN" (radial slot, e.g. a key slot in a bore or on a shaft),
'     BOX    -> a prismatic part instead of a revolved one (e.g. a key),
'     PRISM / CUT <X|Y|Z> a0 a1 <RECT|CIRC|RING|POLY|RPOLY|PATTERN ...> -> prismatic part (links, world
'                            frame): sketch on a plane normal to the axis at a0, extruded / cut to a1;
'     TAP <X|Y|Z> a0 a1 uc vc n pcd M.. ang -> tap-drill holes (thread size in property THREADS),
'     DENSITY kg/m3, PORTP name <X|Y|Z> level dir [key=value] -> interface plane of a prismatic part,
'     COLOR r g b (0..255) -> part colour; without it the colour comes from the part name
'                            (housing, input / output shaft, cup, rotor, stator ...).
'   Every blind cut / extrusion is checked to go to the requested side of its sketch plane.
'   * a JOINT file (joints/*/*.txt) builds a whole joint in one run:
'       USE <role> <component> <file>  - a spec with PARTs (built, inserted as a flexible
'                                        sub-assembly) or a component card with STEP (imported,
'                                        turned so that its axis is X, AXIS + PORT planes added)
'       PARTS <file>                   - parts designed for the joint, in the joint frame
'       PLACE <role> <x> [flip]        - card x=0 of that component at joint x (flip: card +X -> -X)
'       LINK <part> <child part>       - a designed part (3 coincident planes) or an imported body
'                                        (lock mate) moves with a part of a sub-assembly
'     A card with BODY <name> <step> lines gives one part per body (<COMPONENT>-<name>), e.g.
'     rotor and stator of a frameless motor; those STEP files are already in the card frame.
'     The joint frame is the frame of the first USE (the reducer).
'   * a ROBOTASM file (robot/*.txt) builds an assembly of the arm from built models:
'       ROBOTASM <name>                 - assembly name (saved next to the file)
'       REBUILD yes|no                  - rebuild models that already exist (default: no)
'       COMP <name> <file> ox oy oz  xx xy xz  zx zy zz
'                                       - a joint / link / component spec (built if needed, or a
'                                         .SLDASM / .SLDPRT) placed with its origin at (ox,oy,oz)
'                                         and its X / Z axes along the given directions, fixed;
'                                         optional words: rigid (a link) / flex (default for .SLDASM),
'                                         rebuild - build this model again even if it exists (v29)
'       LOCK <comp> <part|-> <comp> <part|->  - instead of fixing: the first component is locked to a part
'                                         of the second (e.g. a link to the output shaft of a joint);
'                                         the joints are flexible, so the arm keeps its degrees of freedom;
'                                         "keep" at the end - the first component stays fixed (only its
'                                         flexible part is locked, e.g. the inner ring of the ОПУ)
'   * a ROBOTANIM file (robot/RTC-7-anim.txt, tools/robot_anim.py) animates the arm:
'       the COMP lines as in ROBOTASM (models built if missing), inserted without mates;
'       FRAME <n> + P <comp> ox oy oz xx xy xz zx zy zz - frame of every component per picture;
'       IMAGES jpg|png|bmp|none - save every frame into <name>-frames\f0000.<ext> (none: only play);
'       VIEW <named view> (default *Isometric), RANGE <first> <last> - frames to run, ZOOM <k> (0.8)
' Files are saved into the folder of the spec file.
'
' Coordinates: X - along the axis of rotation, Y - radius, mm.
' ============================================================================
Option Explicit

Private Const MM As Double = 0.001          ' SolidWorks API works in meters
Private Const PI As Double = 3.14159265358979
Private Const AXIS_NAME As String = "AXIS"
Private Const MACRO_VERSION As String = "v31 (2026-10-24)"
' True: every part / intermediate assembly is closed after it is saved, models for the assemblies are
' loaded without windows; only the result of the run stays open (many open windows hang SolidWorks)
Private Const CLOSE_DOCS As Boolean = True
' True: SolidWorks does not refresh the screen between API calls (faster); set False if a build misbehaves.
' Not used for ROBOTANIM (the view must be redrawn for every saved picture).
Private Const FAST_MODE As Boolean = True

Private Type HoleSpec
    X As Double         ' face position along the axis, mm
    Dir As Integer      ' +1 - drill towards +X, -1 - towards -X
    N As Long           ' number of holes
    Pcd As Double       ' pitch circle diameter, mm
    D As Double         ' hole diameter, mm
    Depth As Double     ' depth, mm (0 = through all)
    Ang As Double       ' angle of the first hole, deg (0 = +Z, 90 = +Y / top)
    IsThread As Boolean ' THREAD line: tapped hole via Hole Wizard
    Size As String      ' thread size for Hole Wizard, e.g. "M4"
    DrillDepth As Double ' tap drill depth, mm (THREAD only)
End Type

Private Type CutSpec        ' FLATS / KEYWAY
    Kind As Integer     ' 1 - FLATS, 2 - KEYWAY
    X As Double         ' start plane, mm
    Dir As Integer      ' +1 / -1 - cut direction along X
    Depth As Double     ' length of the cut along X, mm
    A As Double         ' FLATS: size across flats; KEYWAY: width, mm
    B As Double         ' FLATS: number of flats; KEYWAY: bottom - distance from the axis, mm
    Ang As Double       ' FLATS: normal of the first flat; KEYWAY: slot direction, deg (0 = +Z, 90 = +Y)
    U0 As Double        ' KEYWAY: start of the slot - distance from the axis, mm (0 - from the axis)
End Type

Private Type PartSpec
    Name As String
    PX() As Double
    PY() As Double
    NP As Long
    H() As HoleSpec
    NH As Long
    Motion As Integer   ' 0 - fixed, 1 - rotates about X relative to the first fixed part
    PortName() As String
    PortX() As Double
    PortInfo() As String
    NPort As Long
    Mass As Double      ' kg; 0 - not set
    C() As CutSpec
    NC As Long
    Color As String     ' "r g b" from COLOR, "" - by the part name
    HasBox As Boolean   ' BOX x0 x1 r0 r1 width angle - prism instead of the revolved profile
    BX0 As Double
    BX1 As Double
    BR0 As Double
    BR1 As Double
    BW As Double
    BAng As Double
    ' prismatic part (links): PRISM / CUT operations in the world frame
    NOp As Long
    OpKind() As Integer     ' 1 - PRISM (add), 2 - CUT
    OpAxis() As Integer     ' 0 - X, 1 - Y, 2 - Z (normal of the sketch plane)
    OpA0() As Double        ' sketch plane level along the axis, mm
    OpA1() As Double        ' end level, mm
    OpShape() As String     ' RECT / CIRC / RING / POLY / PATTERN
    OpArgs() As String      ' numbers of the shape, space separated
    Density As Double       ' kg/m3 from DENSITY (0 - not set)
    PortAxis() As Integer   ' -1 - PORT of a revolved part (plane at X), 0..2 - PORTP axis
    Threads As String       ' TAP notes -> custom property THREADS
End Type

Private swApp As SldWorks.SldWorks
Private gParts() As PartSpec
Private gNParts As Long
Private gAsmName As String
Private gTplPart As String        ' templates found once per run (FindTemplate)
Private gTplAsm As String
Private gData As String
Private gPartPaths() As String  ' parts built by the last BuildSpecFile
Private gSummary As String          ' "key=value key=value ..." from DATA lines
Private gLog As String
Private gRebuildAll As Boolean      ' v30: REBUILD yes of an arm - joints rebuild their reducers too
Private gTopSpec As String          ' spec file picked by the user - its result stays open
Private gHidden As Collection       ' models loaded without a window for AddComponent5

Sub main()
    Set swApp = Application.SldWorks
    gLog = "": gSummary = "": gTplPart = "": gTplAsm = "": gRebuildAll = False
    Set gHidden = New Collection

    Dim specPath As String, asmPath As String, ok As Boolean
    specPath = PickSpecFile()
    If specPath = "" Then Exit Sub
    If Not FileExists(specPath) Then
        MsgBox "File not found or bad path:" & vbCrLf & specPath, vbExclamation
        Exit Sub
    End If

    gTopSpec = specPath
    On Error GoTo Crash
    If FAST_MODE And Not FileHasKeyword(specPath, "ROBOTANIM") Then swApp.CommandInProgress = True
    If FileHasKeyword(specPath, "ROBOTANIM") Then
        ok = BuildRobotAnim(specPath)
    ElseIf FileHasKeyword(specPath, "ROBOTASM") Then
        ok = BuildRobotAsm(specPath)
    ElseIf FileHasKeyword(specPath, "JOINT") Then
        ok = BuildJoint(specPath)
    Else
        ok = BuildSpecFile(specPath, asmPath)
    End If
    swApp.CommandInProgress = False
    On Error GoTo 0

    If Not ok Then
        MsgBox "Stopped (" & MACRO_VERSION & ", " & SwVersion() & "):" & vbCrLf & gLog, vbExclamation
    ElseIf gLog <> "" Then
        MsgBox "Finished with warnings (" & MACRO_VERSION & ", " & SwVersion() & "):" & vbCrLf & _
               gSummary & vbCrLf & gLog, vbInformation
    Else
        MsgBox "Done (" & MACRO_VERSION & ", " & SwVersion() & "):" & vbCrLf & gSummary & vbCrLf & _
               "Part template: " & gTplPart & vbCrLf & "Assembly template: " & gTplAsm, vbInformation
    End If
    Exit Sub
Crash:
    swApp.CommandInProgress = False
    MsgBox "Runtime error " & Err.Number & ": " & Err.Description & " (" & MACRO_VERSION & ")" & vbCrLf & gLog, _
           vbCritical
End Sub

' ---------------------------------------------------------------- open / close of documents (CLOSE_DOCS)
Private Function IsTopSpec(ByVal specPath As String) As Boolean
    IsTopSpec = (StrComp(specPath, gTopSpec, vbTextCompare) = 0)
End Function

' Close a saved document (keep = True: it is the result of the run and stays open).
Private Sub CloseSaved(ByVal m As SldWorks.ModelDoc2, ByVal keep As Boolean)
    If Not CLOSE_DOCS Or keep Or m Is Nothing Then Exit Sub
    On Error Resume Next
    swApp.CloseDoc m.GetTitle
    On Error GoTo 0
End Sub

' The model must be loaded for AddComponent5: open it without a window (if it is not open yet)
Private Sub LoadHidden(ByVal path As String)
    Dim d As Object, t As Long, errs As Long, warns As Long
    Set d = swApp.GetOpenDocumentByName(path)
    If Not d Is Nothing Then Exit Sub
    t = IIf(UCase(Right(path, 6)) = "SLDASM", swDocASSEMBLY, swDocPART)
    If CLOSE_DOCS Then swApp.DocumentVisible False, t
    Set d = swApp.OpenDoc6(path, t, swOpenDocOptions_Silent, "", errs, warns)
    If CLOSE_DOCS Then swApp.DocumentVisible True, t
    If Not d Is Nothing And CLOSE_DOCS Then gHidden.Add path
End Sub

' Unload the models loaded by LoadHidden (after the assembly that used them is saved and closed)
Private Sub CloseHidden()
    Dim d As Object
    If Not CLOSE_DOCS Then Exit Sub
    On Error Resume Next
    Do While gHidden.Count > 0
        Set d = swApp.GetOpenDocumentByName(gHidden(1))
        If Not d Is Nothing Then swApp.CloseDoc d.GetTitle
        gHidden.Remove 1
    Loop
    On Error GoTo 0
End Sub

' Parts (and the assembly, if ASSEMBLY is given) of one spec file, saved next to it.
' asmPath returns the assembly path or "". Part paths stay in gPartPaths, the specs in gParts.
Private Function BuildSpecFile(ByVal specPath As String, asmPath As String) As Boolean
    Dim folder As String, i As Long
    asmPath = ""
    If Not ReadSpec(specPath) Then
        gLog = gLog & "Spec not read: " & specPath & vbCrLf
        Exit Function
    End If
    folder = Left(specPath, InStrRev(specPath, "\"))
    ReDim gPartPaths(0 To gNParts - 1)
    For i = 0 To gNParts - 1
        gPartPaths(i) = folder & gParts(i).Name & ".SLDPRT"
        If Not BuildPart(gParts(i), gPartPaths(i)) Then
            gLog = gLog & "Part " & gParts(i).Name & " was not built." & vbCrLf
            Exit Function
        End If
    Next i
    If gAsmName <> "" Then
        asmPath = folder & gAsmName & ".SLDASM"
        BuildAssembly asmPath, gPartPaths, IsTopSpec(specPath)
    ElseIf IsTopSpec(specPath) And CLOSE_DOCS Then       ' parts only: show the last one
        Dim errs As Long, warns As Long
        swApp.OpenDoc6 gPartPaths(gNParts - 1), swDocPART, swOpenDocOptions_Silent, "", errs, warns
    End If
    gSummary = gSummary & Mid(specPath, InStrRev(specPath, "\") + 1) & ": " & gNParts & " part(s)" & _
               IIf(gAsmName <> "", " + assembly " & gAsmName, "") & vbCrLf
    BuildSpecFile = True
End Function

Private Function SwVersion() As String
    Dim rev As String
    rev = swApp.RevisionNumber                          ' e.g. "29.5.1" -> SOLIDWORKS 2021
    SwVersion = "SOLIDWORKS " & SwYear() & " (" & rev & ")"
End Function

' Major revision -> year: 25 -> 2017, 29 -> 2021
Private Function SwYear() As Long
    SwYear = CLng(Val(Split(swApp.RevisionNumber, ".")(0))) + 1992
End Function

' Document template: 1) the default template from Options if the file exists;
' 2) the first *.<ext> in the template folders from Options - File Locations;
' 3) the first *.<ext> in ProgramData\SOLIDWORKS\SOLIDWORKS <year>\templates;
' 4) ask the user to pick a template file.
' Files whose name contains 'hint' (e.g. "part", "assem") are preferred.
Private Function FindTemplate(ByVal ext As String, ByVal pref As Long, ByVal hint As String) As String
    Dim t As String, folders() As String, i As Long, f As String, opts As Long, cfg As String, disp As String
    t = swApp.GetUserPreferenceStringValue(pref)
    If t <> "" Then
        If FileExists(t) Then FindTemplate = t: Exit Function
    End If

    folders = Split(swApp.GetUserPreferenceStringValue(swFileLocationsDocumentTemplates), ";")
    For i = LBound(folders) To UBound(folders)
        f = FirstFile(Trim(folders(i)), ext, hint)
        If f <> "" Then FindTemplate = f: Exit Function
    Next i

    f = FirstFile(Environ("ProgramData") & "\SOLIDWORKS\SOLIDWORKS " & SwYear() & _
                  "\templates", ext, hint)
    If f <> "" Then FindTemplate = f: Exit Function

    On Error Resume Next
    f = swApp.GetOpenFileName("Pick a " & ext & " template", "", "Template (*." & ext & ")|*." & ext & "|", _
                              opts, cfg, disp)
    On Error GoTo 0
    FindTemplate = Trim(Replace(f, """", ""))
End Function

' First file *.<ext> in a folder, preferring names with 'hint'; "" if none
Private Function FirstFile(ByVal folder As String, ByVal ext As String, ByVal hint As String) As String
    Dim nm As String, firstAny As String
    If folder = "" Then Exit Function
    If Right(folder, 1) <> "\" Then folder = folder & "\"
    On Error Resume Next
    nm = Dir(folder & "*." & ext)
    If Err.Number <> 0 Then Exit Function
    On Error GoTo 0
    Do While nm <> ""
        If firstAny = "" Then firstAny = folder & nm
        If InStr(1, nm, hint, vbTextCompare) > 0 Then FirstFile = folder & nm: Exit Function
        nm = Dir
    Loop
    FirstFile = firstAny
End Function

' ---------------------------------------------------------------------------
' Choosing the spec file
' ---------------------------------------------------------------------------
' Standard Open dialog; if it is not available - a text box for the path.
Private Function PickSpecFile() As String
    Dim s As String, opts As Long, cfg As String, disp As String, failed As Boolean
    On Error Resume Next
    s = swApp.GetOpenFileName("Spec file", swApp.GetCurrentMacroPathFolder & "\", _
                              "Spec files (*.txt)|*.txt|All files (*.*)|*.*|", opts, cfg, disp)
    failed = (Err.Number <> 0)
    On Error GoTo 0

    If failed Then
        s = InputBox("Full path to the spec file (*.txt):", "BuildFromSpec", _
                     swApp.GetCurrentMacroPathFolder & "\")
    End If
    ' "Copy as path" in Explorer adds quotes - remove them
    PickSpecFile = Trim(Replace(s, """", ""))
End Function

Private Function FileExists(ByVal path As String) As Boolean
    On Error Resume Next
    FileExists = ((GetAttr(path) And vbDirectory) = 0)
    If Err.Number <> 0 Then FileExists = False
    On Error GoTo 0
End Function

' ---------------------------------------------------------------------------
' Spec reading
' ---------------------------------------------------------------------------
Private Function ReadSpec(ByVal path As String) As Boolean
    Dim s As String, t() As String, lines() As String, li As Long
    Dim lineNo As Long, cur As Long, k As Long, errMsg As String, q As Long, info As String

    cur = -1: gNParts = 0: gAsmName = "": gData = ""
    ReDim gParts(0 To 15)

    lines = ReadLines(path)
    For li = LBound(lines) To UBound(lines)
        lineNo = li + 1
        s = CleanLine(lines(li))
        If s = "" Then GoTo NextLine
        t = Split(s, " ")

        Select Case UCase(t(0))
        Case "ASSEMBLY"
            gAsmName = Trim(Mid(s, 9))

        Case "PART"
            If gNParts > UBound(gParts) Then ReDim Preserve gParts(0 To 2 * gNParts)
            cur = gNParts
            gNParts = gNParts + 1
            gParts(cur).Name = Trim(Mid(s, 5))
            gParts(cur).NP = 0
            gParts(cur).NH = 0
            ReDim gParts(cur).PX(0 To 63)
            ReDim gParts(cur).PY(0 To 63)
            ReDim gParts(cur).H(0 To 15)
            gParts(cur).Motion = 0
            gParts(cur).Mass = 0
            gParts(cur).NC = 0
            ReDim gParts(cur).C(0 To 7)
            gParts(cur).HasBox = False
            gParts(cur).Color = ""
            gParts(cur).NPort = 0
            ReDim gParts(cur).PortName(0 To 7)
            ReDim gParts(cur).PortX(0 To 7)
            ReDim gParts(cur).PortInfo(0 To 7)
            ReDim gParts(cur).PortAxis(0 To 7)
            gParts(cur).NOp = 0
            ReDim gParts(cur).OpKind(0 To 15)
            ReDim gParts(cur).OpAxis(0 To 15)
            ReDim gParts(cur).OpA0(0 To 15)
            ReDim gParts(cur).OpA1(0 To 15)
            ReDim gParts(cur).OpShape(0 To 15)
            ReDim gParts(cur).OpArgs(0 To 15)
            gParts(cur).Density = 0
            gParts(cur).Threads = ""

        Case "END"
            cur = -1

        Case "P"
            If cur < 0 Then errMsg = "'P' outside of PART ... END": GoTo Bad
            If UBound(t) < 2 Then errMsg = "expected 'P x y'": GoTo Bad
            k = gParts(cur).NP
            If k > UBound(gParts(cur).PX) Then
                ReDim Preserve gParts(cur).PX(0 To 2 * k)
                ReDim Preserve gParts(cur).PY(0 To 2 * k)
            End If
            gParts(cur).PX(k) = Num(t(1))
            gParts(cur).PY(k) = Num(t(2))
            If gParts(cur).PY(k) < 0 Then errMsg = "radius (Y) must be >= 0": GoTo Bad
            gParts(cur).NP = k + 1

        Case "HOLES"
            If cur < 0 Then errMsg = "'HOLES' outside of PART ... END": GoTo Bad
            If UBound(t) < 7 Then errMsg = "expected 'HOLES x dir n pcd d depth angle'": GoTo Bad
            k = gParts(cur).NH
            If k > UBound(gParts(cur).H) Then ReDim Preserve gParts(cur).H(0 To 2 * k)
            gParts(cur).H(k).X = Num(t(1))
            gParts(cur).H(k).Dir = IIf(Num(t(2)) < 0, -1, 1)
            gParts(cur).H(k).N = CLng(Num(t(3)))
            gParts(cur).H(k).Pcd = Num(t(4))
            gParts(cur).H(k).D = Num(t(5))
            gParts(cur).H(k).Depth = Num(t(6))
            gParts(cur).H(k).Ang = Num(t(7))
            If gParts(cur).H(k).N < 1 Or gParts(cur).H(k).D <= 0 Then errMsg = "bad hole count or diameter": GoTo Bad
            gParts(cur).NH = k + 1

        Case "THREAD"
            ' THREAD x dir n pcd size threadDepth angle [drillDepth]
            If cur < 0 Then errMsg = "'THREAD' outside of PART ... END": GoTo Bad
            If UBound(t) < 7 Then errMsg = "expected 'THREAD x dir n pcd size depth angle [drillDepth]'": GoTo Bad
            k = gParts(cur).NH
            If k > UBound(gParts(cur).H) Then ReDim Preserve gParts(cur).H(0 To 2 * k)
            gParts(cur).H(k).IsThread = True
            gParts(cur).H(k).X = Num(t(1))
            gParts(cur).H(k).Dir = IIf(Num(t(2)) < 0, -1, 1)
            gParts(cur).H(k).N = CLng(Num(t(3)))
            gParts(cur).H(k).Pcd = Num(t(4))
            gParts(cur).H(k).Size = UCase(t(5))
            gParts(cur).H(k).D = TapDrill(t(5))
            gParts(cur).H(k).Depth = Num(t(6))
            gParts(cur).H(k).Ang = Num(t(7))
            If gParts(cur).H(k).D <= 0 Then errMsg = "unknown thread size '" & t(5) & "'": GoTo Bad
            If gParts(cur).H(k).Depth <= 0 Then errMsg = "thread depth must be > 0": GoTo Bad
            If UBound(t) >= 8 Then
                gParts(cur).H(k).DrillDepth = Num(t(8))
            Else
                gParts(cur).H(k).DrillDepth = gParts(cur).H(k).Depth + 0.5 * Num(Mid(t(5), 2))
            End If
            If gParts(cur).H(k).N < 1 Then errMsg = "bad hole count": GoTo Bad
            gParts(cur).NH = k + 1

        Case "COMPONENT", "TYPE", "STEP", "FRAME"
            ' component card metadata - not used for geometry

        Case "DATA"
            gData = gData & " " & Trim(Mid(s, 5))

        Case "MOTION"
            If cur < 0 Then errMsg = "'MOTION' outside of PART ... END": GoTo Bad
            If UBound(t) < 1 Then errMsg = "expected 'MOTION fixed' or 'MOTION rotate'": GoTo Bad
            Select Case LCase(t(1))
                Case "fixed": gParts(cur).Motion = 0
                Case "rotate": gParts(cur).Motion = 1
                Case Else: errMsg = "expected 'MOTION fixed' or 'MOTION rotate'": GoTo Bad
            End Select

        Case "FLATS", "KEYWAY"
            ' FLATS x0 x1 across [n] [angle]  |  KEYWAY x dir length width bottom angle [from]
            If cur < 0 Then errMsg = "'" & t(0) & "' outside of PART ... END": GoTo Bad
            k = gParts(cur).NC
            If k > UBound(gParts(cur).C) Then ReDim Preserve gParts(cur).C(0 To 2 * k)
            If UCase(t(0)) = "FLATS" Then
                If UBound(t) < 3 Then errMsg = "expected 'FLATS x0 x1 across [n] [angle]'": GoTo Bad
                gParts(cur).C(k).Kind = 1
                gParts(cur).C(k).X = Num(t(1))
                gParts(cur).C(k).Dir = IIf(Num(t(2)) < Num(t(1)), -1, 1)
                gParts(cur).C(k).Depth = Abs(Num(t(2)) - Num(t(1)))
                gParts(cur).C(k).A = Num(t(3))
                gParts(cur).C(k).B = 4
                If UBound(t) >= 4 Then gParts(cur).C(k).B = Num(t(4))
                gParts(cur).C(k).Ang = 0
                If UBound(t) >= 5 Then gParts(cur).C(k).Ang = Num(t(5))
                If gParts(cur).C(k).B < 1 Or gParts(cur).C(k).A <= 0 Then errMsg = "bad FLATS size or count": GoTo Bad
            Else
                If UBound(t) < 6 Then errMsg = "expected 'KEYWAY x dir length width bottom angle'": GoTo Bad
                gParts(cur).C(k).Kind = 2
                gParts(cur).C(k).X = Num(t(1))
                gParts(cur).C(k).Dir = IIf(Num(t(2)) < 0, -1, 1)
                gParts(cur).C(k).Depth = Num(t(3))
                gParts(cur).C(k).A = Num(t(4))
                gParts(cur).C(k).B = Num(t(5))
                gParts(cur).C(k).Ang = Num(t(6))
                gParts(cur).C(k).U0 = 0
                If UBound(t) >= 7 Then gParts(cur).C(k).U0 = Num(t(7))
                If gParts(cur).C(k).A <= 0 Or gParts(cur).C(k).B <= gParts(cur).C(k).U0 Then errMsg = "bad KEYWAY width, bottom or from": GoTo Bad
            End If
            If gParts(cur).C(k).Depth <= 0 Then errMsg = "cut length must be > 0": GoTo Bad
            gParts(cur).NC = k + 1

        Case "BOX"
            ' BOX x0 x1 r0 r1 width angle: rectangle r0..r1 (from the axis) x width, direction angle, x0..x1
            If cur < 0 Then errMsg = "'BOX' outside of PART ... END": GoTo Bad
            If UBound(t) < 6 Then errMsg = "expected 'BOX x0 x1 r0 r1 width angle'": GoTo Bad
            gParts(cur).HasBox = True
            gParts(cur).BX0 = Num(t(1)): gParts(cur).BX1 = Num(t(2))
            gParts(cur).BR0 = Num(t(3)): gParts(cur).BR1 = Num(t(4))
            gParts(cur).BW = Num(t(5)): gParts(cur).BAng = Num(t(6))
            If gParts(cur).BX1 = gParts(cur).BX0 Or gParts(cur).BR1 <= gParts(cur).BR0 Or gParts(cur).BW <= 0 Then _
                errMsg = "bad BOX size": GoTo Bad

        Case "COLOR"
            If cur < 0 Then errMsg = "'COLOR' outside of PART ... END": GoTo Bad
            If UBound(t) < 3 Then errMsg = "expected 'COLOR r g b' (0..255)": GoTo Bad
            gParts(cur).Color = t(1) & " " & t(2) & " " & t(3)

        Case "MASS"
            If cur < 0 Then errMsg = "'MASS' outside of PART ... END": GoTo Bad
            If UBound(t) < 1 Then errMsg = "expected 'MASS kg'": GoTo Bad
            gParts(cur).Mass = Num(t(1))
            If gParts(cur).Mass <= 0 Then errMsg = "mass must be > 0": GoTo Bad

        Case "PORT"
            ' PORT name x dir [key=value ...]; outside PART (purchased parts) - ignored
            If cur >= 0 Then
                If UBound(t) < 3 Then errMsg = "expected 'PORT name x dir [key=value ...]'": GoTo Bad
                k = gParts(cur).NPort
                If k > UBound(gParts(cur).PortName) Then
                    ReDim Preserve gParts(cur).PortName(0 To 2 * k)
                    ReDim Preserve gParts(cur).PortX(0 To 2 * k)
                    ReDim Preserve gParts(cur).PortInfo(0 To 2 * k)
                    ReDim Preserve gParts(cur).PortAxis(0 To 2 * k)
                End If
                gParts(cur).PortName(k) = t(1)
                gParts(cur).PortX(k) = Num(t(2))
                gParts(cur).PortAxis(k) = -1
                info = "x=" & t(2) & " dir=" & t(3)
                For q = 4 To UBound(t)
                    info = info & " " & t(q)
                Next q
                gParts(cur).PortInfo(k) = info
                gParts(cur).NPort = k + 1
            End If
        Case "PRISM", "CUT", "TAP"
            ' PRISM|CUT axis a0 a1 shape numbers... | TAP axis a0 a1 uc vc n pcd Msize ang
            If cur < 0 Then errMsg = "'" & t(0) & "' outside of PART ... END": GoTo Bad
            If UBound(t) < 5 Then errMsg = "expected '" & t(0) & " X|Y|Z a0 a1 ...'": GoTo Bad
            k = gParts(cur).NOp
            If k > UBound(gParts(cur).OpKind) Then
                ReDim Preserve gParts(cur).OpKind(0 To 2 * k)
                ReDim Preserve gParts(cur).OpAxis(0 To 2 * k)
                ReDim Preserve gParts(cur).OpA0(0 To 2 * k)
                ReDim Preserve gParts(cur).OpA1(0 To 2 * k)
                ReDim Preserve gParts(cur).OpShape(0 To 2 * k)
                ReDim Preserve gParts(cur).OpArgs(0 To 2 * k)
            End If
            gParts(cur).OpAxis(k) = InStr("XYZ", UCase(t(1))) - 1
            If gParts(cur).OpAxis(k) < 0 Or Len(t(1)) <> 1 Then errMsg = "axis must be X, Y or Z": GoTo Bad
            gParts(cur).OpA0(k) = Num(t(2))
            gParts(cur).OpA1(k) = Num(t(3))
            If gParts(cur).OpA0(k) = gParts(cur).OpA1(k) Then errMsg = "a0 = a1": GoTo Bad
            info = ""
            If UCase(t(0)) = "TAP" Then
                If UBound(t) < 9 Then errMsg = "expected 'TAP axis a0 a1 uc vc n pcd Msize ang'": GoTo Bad
                If TapDrill(t(8)) <= 0 Then errMsg = "unknown thread size '" & t(8) & "'": GoTo Bad
                gParts(cur).OpKind(k) = 2
                gParts(cur).OpShape(k) = "PATTERN"
                info = t(4) & " " & t(5) & " " & t(6) & " " & t(7) & " " & CStr(TapDrill(t(8))) & " " & t(9)
                gParts(cur).Threads = gParts(cur).Threads & IIf(gParts(cur).Threads = "", "", "; ") & _
                    t(6) & "x" & UCase(t(8)) & " PCD" & t(7) & " " & UCase(t(1)) & t(2) & ".." & t(3)
            Else
                gParts(cur).OpKind(k) = IIf(UCase(t(0)) = "PRISM", 1, 2)
                gParts(cur).OpShape(k) = UCase(t(4))
                For q = 5 To UBound(t)
                    info = info & IIf(info = "", "", " ") & t(q)
                Next q
                Select Case gParts(cur).OpShape(k)
                    Case "RECT": If UBound(t) < 8 Then errMsg = "RECT u0 u1 v0 v1": GoTo Bad
                    Case "CIRC": If UBound(t) < 7 Then errMsg = "CIRC uc vc D": GoTo Bad
                    Case "RING": If UBound(t) < 8 Then errMsg = "RING uc vc D d": GoTo Bad
                    Case "PATTERN": If UBound(t) < 10 Then errMsg = "PATTERN uc vc n pcd d ang": GoTo Bad
                    Case "POLY": If UBound(t) < 10 Or ((UBound(t) - 4) Mod 2) <> 0 Then errMsg = "POLY u1 v1 u2 v2 u3 v3 ...": GoTo Bad
                    Case "RPOLY": If UBound(t) < 13 Or ((UBound(t) - 4) Mod 3) <> 0 Then errMsg = "RPOLY u1 v1 r1 u2 v2 r2 u3 v3 r3 ...": GoTo Bad
                    Case Else: errMsg = "unknown shape '" & t(4) & "'": GoTo Bad
                End Select
            End If
            gParts(cur).OpArgs(k) = info
            gParts(cur).NOp = k + 1

        Case "DENSITY"
            If cur < 0 Then errMsg = "'DENSITY' outside of PART ... END": GoTo Bad
            If UBound(t) < 1 Then errMsg = "expected 'DENSITY kg/m3'": GoTo Bad
            gParts(cur).Density = Num(t(1))

        Case "PORTP"
            ' PORTP name axis level dir [key=value ...]
            If cur < 0 Then errMsg = "'PORTP' outside of PART ... END": GoTo Bad
            If UBound(t) < 4 Then errMsg = "expected 'PORTP name X|Y|Z level dir [key=value ...]'": GoTo Bad
            k = gParts(cur).NPort
            If k > UBound(gParts(cur).PortName) Then
                ReDim Preserve gParts(cur).PortName(0 To 2 * k)
                ReDim Preserve gParts(cur).PortX(0 To 2 * k)
                ReDim Preserve gParts(cur).PortInfo(0 To 2 * k)
                ReDim Preserve gParts(cur).PortAxis(0 To 2 * k)
            End If
            gParts(cur).PortName(k) = t(1)
            gParts(cur).PortAxis(k) = InStr("XYZ", UCase(t(2))) - 1
            If gParts(cur).PortAxis(k) < 0 Then errMsg = "axis must be X, Y or Z": GoTo Bad
            gParts(cur).PortX(k) = Num(t(3))
            info = LCase(t(2)) & "=" & t(3) & " dir=" & t(4)
            For q = 5 To UBound(t)
                info = info & " " & t(q)
            Next q
            gParts(cur).PortInfo(k) = info
            gParts(cur).NPort = k + 1

        Case "ROBOT", "UNITS", "AXIS", "FLANGE", "CABLE"
            ' layout lines - not geometry of a part

        Case Else
            errMsg = "unknown keyword '" & t(0) & "'": GoTo Bad
        End Select
NextLine:
    Next li

    If gNParts = 0 Then
        Dim firstLine As String
        For li = LBound(lines) To UBound(lines)
            If Trim(lines(li)) <> "" Then firstLine = lines(li): Exit For
        Next li
        MsgBox "No PART found in the spec." & vbCrLf & vbCrLf & _
               "Macro: " & MACRO_VERSION & vbCrLf & _
               "File: " & path & vbCrLf & _
               "Size: " & FileLen(path) & " bytes, lines read: " & (UBound(lines) - LBound(lines) + 1) & vbCrLf & _
               "First line: " & Left(firstLine, 80), vbExclamation
        Exit Function
    End If
    For cur = 0 To gNParts - 1
        k = gParts(cur).NP
        If k > 1 Then
            If gParts(cur).PX(k - 1) = gParts(cur).PX(0) And _
               gParts(cur).PY(k - 1) = gParts(cur).PY(0) Then gParts(cur).NP = k - 1
        End If
        If gParts(cur).NP < 3 And Not gParts(cur).HasBox And gParts(cur).NOp = 0 Then
            MsgBox "Part " & gParts(cur).Name & ": profile needs at least 3 points.", vbExclamation
            Exit Function
        End If
    Next cur
    ReadSpec = True
    Exit Function

Bad:
    MsgBox "Spec line " & lineNo & ": " & errMsg, vbExclamation
End Function

' Whole file -> array of lines. Works with Windows (CRLF), Unix (LF) and old Mac (CR)
' line endings and skips a UTF-8 BOM (Line Input does not understand LF-only files).
Private Function ReadLines(ByVal path As String) As String()
    Dim f As Integer, content As String
    f = FreeFile
    Open path For Binary Access Read As #f
    content = Space$(LOF(f))
    Get #f, , content
    Close #f
    If Left$(content, 3) = Chr$(239) & Chr$(187) & Chr$(191) Then content = Mid$(content, 4)
    content = Replace(content, vbCrLf, vbLf)
    content = Replace(content, vbCr, vbLf)
    ReadLines = Split(content, vbLf)
End Function

Private Function CleanLine(ByVal s As String) As String
    Dim p As Long
    p = InStr(s, "#")
    If p > 0 Then s = Left(s, p - 1)
    p = InStr(s, ";")
    If p > 0 Then s = Left(s, p - 1)
    s = Trim(Replace(s, vbTab, " "))
    Do While InStr(s, "  ") > 0
        s = Replace(s, "  ", " ")
    Loop
    CleanLine = s
End Function

Private Function Num(ByVal s As String) As Double
    Num = Val(Replace(s, ",", "."))
End Function

' ---------------------------------------------------------------------------
' Part
' ---------------------------------------------------------------------------
Private Function BuildPart(p As PartSpec, ByVal outPath As String) As Boolean
    Dim m As SldWorks.ModelDoc2
    If gTplPart = "" Then gTplPart = FindTemplate("prtdot", swDefaultTemplatePart, "part")
    If gTplPart <> "" Then Set m = swApp.NewDocument(gTplPart, 0, 0, 0)
    If m Is Nothing Then
        gLog = gLog & "Cannot create a part from the template:" & vbCrLf & "  '" & gTplPart & "'" & vbCrLf & _
               "Set it in Options - Default Templates (Part) or pick a *.prtdot when asked." & vbCrLf
        Exit Function
    End If

    Dim planes(0 To 2) As SldWorks.Feature    ' Front, Top, Right
    If Not GetRefPlanes(m.FirstFeature, planes) Then
        gLog = gLog & "Reference planes not found in the part template." & vbCrLf
        Exit Function
    End If

    Dim body As SldWorks.Feature
    If p.NOp > 0 Then
        If Not BuildPrismatic(m, planes, p) Then Exit Function
        If p.Density > 0 Then m.SetUserPreferenceDoubleValue swMaterialPropertyDensity, p.Density
        If p.Mass > 0 Then SetPartMass m, p
        If p.Threads <> "" Then SetProp m, "THREADS", p.Threads
        Dim ip As Long
        For ip = 0 To p.NPort - 1
            If p.PortAxis(ip) >= 0 Then AddPortP m, planes, p, ip Else AddPort m, planes(2), p, ip
        Next ip
        GoTo Finish
    End If
    If p.HasBox Then
        Set body = AddBox(m, planes(2), p)
        If body Is Nothing Then Exit Function
        GoTo BodyDone
    End If

    ' --- profile sketch on the Front plane ---
    Dim sm As SldWorks.SketchManager
    Set sm = m.SketchManager
    m.ClearSelection2 True
    planes(0).Select2 False, 0
    sm.InsertSketch True
    SnapOff sm, True        ' short segments (thin lips) must not snap to their neighbours

    Dim i As Long, j As Long, xMin As Double, xMax As Double
    xMin = p.PX(0): xMax = p.PX(0)
    For i = 0 To p.NP - 1
        j = (i + 1) Mod p.NP
        sm.CreateLine p.PX(i) * MM, p.PY(i) * MM, 0, p.PX(j) * MM, p.PY(j) * MM, 0
        If p.PX(i) < xMin Then xMin = p.PX(i)
        If p.PX(i) > xMax Then xMax = p.PX(i)
    Next i
    sm.CreateCenterLine xMin * MM, 0, 0, xMax * MM, 0, 0
    SnapOff sm, False
    sm.InsertSketch True

    Dim sk As SldWorks.Feature
    Set sk = m.FeatureByPositionReverse(0)
    sk.Name = "Profile"

    ' --- revolve ---
    m.ClearSelection2 True
    sk.Select2 False, 0
    Set body = m.FeatureManager.FeatureRevolve2( _
        True, True, False, False, False, False, _
        swEndCondBlind, swEndCondBlind, 2 * PI, 0, _
        False, False, 0, 0, _
        swThinWallOneDirection, 0, 0, _
        True, False, True)
    If body Is Nothing Then
        gLog = gLog & p.Name & ": revolve failed (profile not closed or self-intersecting?)" & vbCrLf
        Exit Function
    End If
BodyDone:
    body.Name = "Body"

    ' --- flats and keyways ---
    For i = 0 To p.NC - 1
        AddCut m, planes(2), p, i
    Next i

    ' --- holes ---
    For i = 0 To p.NH - 1
        If p.H(i).IsThread Then
            AddThread m, planes, p, i
        Else
            AddHoles m, planes(2), p.H(i), i + 1, p.Name
        End If
    Next i

    ' --- mass (uniform density so that the part has the given mass) ---
    If p.Mass > 0 Then SetPartMass m, p

    ' --- axis of rotation and interface planes ---
    AddAxis m, planes, p.Name
    For i = 0 To p.NPort - 1
        AddPort m, planes(2), p, i
    Next i

Finish:
    m.ClearSelection2 True
    m.EditRebuild3
    m.ShowNamedView2 "*Isometric", swIsometricView
    m.ViewZoomtofit2

    ApplyColor m, p.Name, p.Color
    If Not SaveDoc(m, outPath) Then Exit Function
    CloseSaved m, False
    BuildPart = True
End Function

' FLATS: region between a big circle and a regular polygon (n flats) is cut over the length.
' KEYWAY: rectangle from the axis to "bottom", "width" wide, in the direction Ang.
Private Sub AddCut(ByVal m As SldWorks.ModelDoc2, ByVal rightPlane As SldWorks.Feature, _
                   p As PartSpec, ByVal i As Long)
    Dim c As CutSpec, pl As SldWorks.Feature, nm As String
    c = p.C(i)
    nm = IIf(c.Kind = 1, "Flats", "Keyway") & (i + 1)
    Set pl = GetOffsetPlane(m, rightPlane, c.X)
    If pl Is Nothing Then
        gLog = gLog & p.Name & ": cannot create plane at X=" & c.X & " for " & nm & vbCrLf
        Exit Sub
    End If

    Dim sm As SldWorks.SketchManager, xf As SldWorks.MathTransform
    Dim k As Long, n As Long, rv As Double, a As Double, rMax As Double
    Dim pt(0 To 3) As Variant, p1 As Variant, p2 As Variant
    Set sm = m.SketchManager
    m.ClearSelection2 True
    pl.Select2 False, 0
    sm.InsertSketch True
    Set xf = sm.ActiveSketch.ModelToSketchTransform
    SnapOff sm, True

    If c.Kind = 1 Then
        n = CLng(c.B)
        rv = c.A / 2 / Cos(PI / n)                     ' polygon vertex radius
        For k = 0 To n - 1
            p1 = PolarPt(xf, c.X, rv, c.Ang + 180# / n + k * 360# / n)
            p2 = PolarPt(xf, c.X, rv, c.Ang + 180# / n + (k + 1) * 360# / n)
            sm.CreateLine p1(0), p1(1), 0, p2(0), p2(1), 0
        Next k
        For k = 0 To p.NP - 1
            If p.PY(k) > rMax Then rMax = p.PY(k)
        Next k
        p1 = PolarPt(xf, c.X, 0, 0)
        sm.CreateCircleByRadius p1(0), p1(1), 0, 2 * rMax * MM
    Else
        ' corners in (radial u, tangential v): (0,-w/2) (bottom,-w/2) (bottom,w/2) (0,w/2)
        a = c.Ang * PI / 180#
        pt(0) = SlotPt(xf, c.X, c.U0, -c.A / 2, a)
        pt(1) = SlotPt(xf, c.X, c.B, -c.A / 2, a)
        pt(2) = SlotPt(xf, c.X, c.B, c.A / 2, a)
        pt(3) = SlotPt(xf, c.X, c.U0, c.A / 2, a)
        For k = 0 To 3
            sm.CreateLine pt(k)(0), pt(k)(1), 0, pt((k + 1) Mod 4)(0), pt((k + 1) Mod 4)(1), 0
        Next k
    End If
    SnapOff sm, False
    sm.InsertSketch True

    Dim sk As SldWorks.Feature, cut As SldWorks.Feature, attempt As Long, rev As Boolean
    Set sk = m.FeatureByPositionReverse(0)
    sk.Name = nm & "_Sketch"
    For attempt = 0 To 1
        rev = (c.Dir < 0) Xor (attempt = 1)
        m.ClearSelection2 True
        sk.Select2 False, 0
        Set cut = CutExtrude(m, True, rev, swEndCondBlind, c.Depth * MM)
        If Not cut Is Nothing Then
            If CutSide(cut, c.X, c.Dir) Then Exit For
            DeleteFeature m, cut                    ' went to the wrong side of the plane
        End If
    Next attempt
    If cut Is Nothing Then
        gLog = gLog & p.Name & ": " & nm & " failed (X=" & c.X & ")" & vbCrLf
    Else
        cut.Name = nm
    End If
End Sub

' Sketch entities straight into the database: no snapping / automatic relations to the
' edges of the face the sketch lies on (snapping depends on the zoom and moved holes).
Private Sub SnapOff(ByVal sm As SldWorks.SketchManager, ByVal onOff As Boolean)
    sm.AddToDB = onOff
    sm.DisplayWhenAdded = Not onOff
End Sub

' True if the faces of a cut reach beyond its sketch plane X = x on the side dir
' (the default direction of a cut is not the same as of a boss - so it is checked, not assumed)
Private Function CutSide(ByVal cut As Object, ByVal x As Double, ByVal dir As Integer) As Boolean
    Dim faces As Variant, fc As Variant, bx As Variant, lo As Double, hi As Double
    lo = 1E+30: hi = -1E+30
    faces = cut.GetFaces
    If IsEmpty(faces) Then CutSide = True: Exit Function
    For Each fc In faces
        bx = fc.GetBox
        If bx(0) < lo Then lo = bx(0)
        If bx(3) > hi Then hi = bx(3)
    Next fc
    If dir > 0 Then
        CutSide = (hi > x * MM + 0.00001)
    Else
        CutSide = (lo < x * MM - 0.00001)
    End If
End Function

Private Sub DeleteFeature(ByVal m As SldWorks.ModelDoc2, ByVal f As Object)
    m.ClearSelection2 True
    f.Select2 False, 0
    m.EditDelete
    m.ClearSelection2 True
End Sub

' BOX part: rectangle (radial BR0..BR1, BW wide, direction BAng) on the plane X = BX0, extruded to BX1.
' The side of the extrusion is checked by the part box.
Private Function AddBox(ByVal m As SldWorks.ModelDoc2, ByVal rightPlane As SldWorks.Feature, _
                        p As PartSpec) As SldWorks.Feature
    Dim pl As SldWorks.Feature, sm As SldWorks.SketchManager, xf As SldWorks.MathTransform
    Dim pt(0 To 3) As Variant, k As Long, a As Double, sk As SldWorks.Feature
    Dim fm As Object, f As Object, attempt As Long, bx As Variant, lo As Double, hi As Double
    Set pl = GetOffsetPlane(m, rightPlane, p.BX0)
    If pl Is Nothing Then
        gLog = gLog & p.Name & ": cannot create plane at X=" & p.BX0 & " for BOX" & vbCrLf
        Exit Function
    End If
    Set sm = m.SketchManager
    m.ClearSelection2 True
    pl.Select2 False, 0
    sm.InsertSketch True
    Set xf = sm.ActiveSketch.ModelToSketchTransform
    SnapOff sm, True
    a = p.BAng * PI / 180#
    pt(0) = SlotPt(xf, p.BX0, p.BR0, -p.BW / 2, a)
    pt(1) = SlotPt(xf, p.BX0, p.BR1, -p.BW / 2, a)
    pt(2) = SlotPt(xf, p.BX0, p.BR1, p.BW / 2, a)
    pt(3) = SlotPt(xf, p.BX0, p.BR0, p.BW / 2, a)
    For k = 0 To 3
        sm.CreateLine pt(k)(0), pt(k)(1), 0, pt((k + 1) Mod 4)(0), pt((k + 1) Mod 4)(1), 0
    Next k
    SnapOff sm, False
    sm.InsertSketch True
    Set sk = m.FeatureByPositionReverse(0)
    sk.Name = "Box_Sketch"

    lo = IIf(p.BX0 < p.BX1, p.BX0, p.BX1) * MM
    hi = IIf(p.BX0 < p.BX1, p.BX1, p.BX0) * MM
    Set fm = m.FeatureManager
    For attempt = 0 To 1
        m.ClearSelection2 True
        sk.Select2 False, 0
        On Error Resume Next
        Set f = Nothing
        Set f = fm.FeatureExtrusion2(True, False, (attempt = 1), swEndCondBlind, swEndCondBlind, _
                                     hi - lo, 0, False, False, False, False, 0, 0, _
                                     False, False, False, False, True, True, True, 0, 0, False)
        On Error GoTo 0
        If Not f Is Nothing Then
            m.EditRebuild3
            bx = PartBox(m)
            If Abs(bx(0) - lo) < 0.00001 And Abs(bx(3) - hi) < 0.00001 Then
                Set AddBox = f
                Exit Function
            End If
            DeleteFeature m, f
        End If
    Next attempt
    gLog = gLog & p.Name & ": BOX extrusion failed" & vbCrLf
End Function

' Part colour: "r g b" (0..255) or, if empty, by keywords in the part name
Private Sub ApplyColor(ByVal m As SldWorks.ModelDoc2, ByVal nm As String, ByVal rgb As String)
    Dim t() As String, r As Double, g As Double, b As Double, v(0 To 8) As Double
    If rgb <> "" Then
        t = Split(rgb, " ")
        r = Num(t(0)): g = Num(t(1)): b = Num(t(2))
    Else
        DefaultColor nm, r, g, b
    End If
    v(0) = r / 255: v(1) = g / 255: v(2) = b / 255
    v(3) = 1: v(4) = 1: v(5) = 0.4: v(6) = 0.3: v(7) = 0: v(8) = 0   ' ambient, diffuse, specular, shininess, transparency, emission
    On Error Resume Next
    m.MaterialPropertyValues = v
    If Err.Number <> 0 Then gLog = gLog & nm & ": colour not set" & vbCrLf
    On Error GoTo 0
End Sub

Private Sub DefaultColor(ByVal nm As String, r As Double, g As Double, b As Double)
    Dim n As String
    n = LCase(nm)
    If InStr(n, "motorhousing") > 0 Then
        r = 176: g = 186: b = 196          ' light steel
    ElseIf InStr(n, "statorclamp") > 0 Then
        r = 230: g = 190: b = 60           ' yellow
    ElseIf InStr(n, "rotorcup") > 0 Then
        r = 200: g = 80: b = 70            ' red
    ElseIf InStr(n, "clampflange") > 0 Then
        r = 150: g = 100: b = 200          ' violet
    ElseIf InStr(n, "coupling") > 0 Then
        r = 110: g = 90: b = 210           ' blue-violet
    ElseIf InStr(n, "_key") > 0 Then
        r = 60: g = 60: b = 60             ' dark
    ElseIf InStr(n, "adapterplate") > 0 Then
        r = 70: g = 160: b = 160           ' teal
    ElseIf InStr(n, "inputshaft") > 0 Then
        r = 240: g = 150: b = 40           ' orange
    ElseIf InStr(n, "outputshaft") > 0 Then
        r = 90: g = 170: b = 90            ' green
    ElseIf InStr(n, "housing") > 0 Then
        r = 110: g = 130: b = 150          ' reducer housing: blue-grey
    ElseIf Right(n, 6) = "-rotor" Then
        r = 184: g = 115: b = 51           ' copper
    ElseIf Right(n, 7) = "-stator" Then
        r = 75: g = 75: b = 90             ' dark grey
    ElseIf InStr(n, "ak80") > 0 Then
        r = 45: g = 45: b = 50             ' actuator: black
    Else
        Select Case Len(n) Mod 4           ' anything else: a few calm colours
            Case 0: r = 120: g = 160: b = 210
            Case 1: r = 210: g = 160: b = 120
            Case 2: r = 140: g = 190: b = 140
            Case Else: r = 190: g = 140: b = 180
        End Select
    End If
End Sub

' Point at radius r (mm), angle angDeg (0 = +Z, 90 = +Y) in the plane X = x -> sketch coordinates
Private Function PolarPt(ByVal xf As SldWorks.MathTransform, ByVal x As Double, _
                         ByVal r As Double, ByVal angDeg As Double) As Variant
    Dim a As Double
    a = angDeg * PI / 180#
    PolarPt = ModelToSketch(xf, x * MM, r * Sin(a) * MM, r * Cos(a) * MM)
End Function

' Point u along the radial direction a (rad) and v across it, mm -> sketch coordinates
Private Function SlotPt(ByVal xf As SldWorks.MathTransform, ByVal x As Double, _
                        ByVal u As Double, ByVal v As Double, ByVal a As Double) As Variant
    SlotPt = ModelToSketch(xf, x * MM, (u * Sin(a) + v * Cos(a)) * MM, (u * Cos(a) - v * Sin(a)) * MM)
End Function

' Circular pattern of holes as one sketch + one Cut-Extrude
Private Sub AddHoles(ByVal m As SldWorks.ModelDoc2, ByVal rightPlane As SldWorks.Feature, _
                     h As HoleSpec, ByVal idx As Long, ByVal partName As String)
    Dim pl As SldWorks.Feature
    Set pl = GetOffsetPlane(m, rightPlane, h.X)
    If pl Is Nothing Then
        gLog = gLog & partName & ": cannot create plane at X=" & h.X & vbCrLf
        Exit Sub
    End If

    Dim sm As SldWorks.SketchManager, i As Long, a As Double
    Dim xf As SldWorks.MathTransform, sp As Variant
    Set sm = m.SketchManager
    m.ClearSelection2 True
    pl.Select2 False, 0
    sm.InsertSketch True
    Set xf = sm.ActiveSketch.ModelToSketchTransform
    SnapOff sm, True        ' no snapping to edges of the face under the sketch
    For i = 0 To h.N - 1
        a = (h.Ang + i * 360# / h.N) * PI / 180#
        ' hole centre in model coordinates -> sketch coordinates
        sp = ModelToSketch(xf, h.X * MM, h.Pcd / 2 * Sin(a) * MM, h.Pcd / 2 * Cos(a) * MM)
        sm.CreateCircleByRadius sp(0), sp(1), 0, h.D / 2 * MM
    Next i
    SnapOff sm, False
    sm.InsertSketch True

    Dim sk As SldWorks.Feature
    Set sk = m.FeatureByPositionReverse(0)
    sk.Name = "Holes" & idx & "_Sketch"

    Dim cut As SldWorks.Feature, attempt As Long, rev As Boolean
    If h.Depth <= 0 Then
        m.ClearSelection2 True
        sk.Select2 False, 0
        Set cut = CutExtrude(m, False, False, swEndCondThroughAll, 0.01)
        If cut Is Nothing Then            ' fallback: blind 0.5 m in both directions
            m.ClearSelection2 True
            sk.Select2 False, 0
            Set cut = CutExtrude(m, False, False, swEndCondBlind, 0.5)
        End If
    Else
        ' first try the given direction; if the cut misses the body, try the other one
        For attempt = 0 To 1
            rev = (h.Dir < 0) Xor (attempt = 1)
            m.ClearSelection2 True
            sk.Select2 False, 0
            Set cut = CutExtrude(m, True, rev, swEndCondBlind, h.Depth * MM)
            If Not cut Is Nothing Then
                If CutSide(cut, h.X, h.Dir) Then Exit For
                DeleteFeature m, cut                ' went to the wrong side of the plane
            End If
        Next attempt
    End If

    If cut Is Nothing Then
        gLog = gLog & partName & ": holes #" & idx & " failed (X=" & h.X & ", D=" & h.D & ")" & vbCrLf
    Else
        cut.Name = "Holes" & idx
    End If
End Sub

Private Function CutExtrude(ByVal m As SldWorks.ModelDoc2, ByVal singleDir As Boolean, _
                            ByVal reverseDir As Boolean, ByVal endCond As Long, _
                            ByVal depth As Double) As SldWorks.Feature
    Set CutExtrude = m.FeatureManager.FeatureCut3( _
        singleDir, False, reverseDir, endCond, endCond, depth, depth, _
        False, False, False, False, 0, 0, _
        False, False, False, False, _
        False, True, True, True, True, False, _
        swStartSketchPlane, 0, False)
End Function

' Plane parallel to Right (YZ) at distance X from the origin; reused if it exists
Private Function GetOffsetPlane(ByVal m As SldWorks.ModelDoc2, ByVal rightPlane As SldWorks.Feature, _
                                ByVal x As Double) As SldWorks.Feature
    If Abs(x) < 0.000001 Then
        Set GetOffsetPlane = rightPlane
        Exit Function
    End If

    Dim nm As String, pd As SldWorks.PartDoc, f As SldWorks.Feature
    nm = "Plane_X" & Replace(CStr(x), ",", ".")
    Set pd = m
    Set f = pd.FeatureByName(nm)
    If Not f Is Nothing Then
        Set GetOffsetPlane = f
        Exit Function
    End If

    Set f = NewPlaneAtX(m, rightPlane, x)
    If f Is Nothing Then Exit Function

    f.Name = nm
    m.ClearSelection2 True
    f.Select2 False, 0
    m.BlankRefGeom          ' hide the helper plane
    m.ClearSelection2 True
    Set GetOffsetPlane = f
End Function

' New plane parallel to Right (YZ) at X (coincident with Right when X = 0)
Private Function NewPlaneAtX(ByVal m As SldWorks.ModelDoc2, ByVal rightPlane As SldWorks.Feature, _
                             ByVal x As Double) As SldWorks.Feature
    Dim f As SldWorks.Feature, rp As SldWorks.RefPlane
    m.ClearSelection2 True
    rightPlane.Select2 False, 0
    If Abs(x) < 0.000001 Then
        Set rp = m.FeatureManager.InsertRefPlane(swRefPlaneReferenceConstraint_Coincident, 0, 0, 0, 0, 0)
        If rp Is Nothing Then Exit Function
        Set NewPlaneAtX = m.FeatureByPositionReverse(0)
        m.ClearSelection2 True
        Exit Function
    End If

    Set rp = m.FeatureManager.InsertRefPlane(swRefPlaneReferenceConstraint_Distance, Abs(x) * MM, 0, 0, 0, 0)
    If rp Is Nothing Then Exit Function
    Set f = m.FeatureByPositionReverse(0)

    ' make sure the plane went to the right side of the origin
    If Sgn(PlaneX(rp)) <> Sgn(x) Then
        m.ClearSelection2 True
        f.Select2 False, 0
        m.EditDelete
        m.ClearSelection2 True
        rightPlane.Select2 False, 0
        Set rp = m.FeatureManager.InsertRefPlane( _
            swRefPlaneReferenceConstraint_Distance + swRefPlaneReferenceConstraint_OptionFlip, _
            Abs(x) * MM, 0, 0, 0, 0)
        If rp Is Nothing Then Exit Function
        Set f = m.FeatureByPositionReverse(0)
    End If
    m.ClearSelection2 True
    Set NewPlaneAtX = f
End Function

' Part mass from MASS: document density = mass / volume (uniform material, so the
' centre of mass and inertia follow the geometry). Works when the part template has
' no material assigned; otherwise the mass properties are overridden.
Private Sub SetPartMass(ByVal m As SldWorks.ModelDoc2, p As PartSpec)
    Dim mp As Object, vol As Double, got As Double
    m.EditRebuild3
    Set mp = m.Extension.CreateMassProperty
    If mp Is Nothing Then
        gLog = gLog & p.Name & ": mass properties not available, MASS not applied" & vbCrLf
        Exit Sub
    End If
    vol = mp.Volume                                     ' m^3
    If vol <= 0 Then
        gLog = gLog & p.Name & ": zero volume, MASS not applied" & vbCrLf
        Exit Sub
    End If
    m.SetUserPreferenceDoubleValue swMaterialPropertyDensity, p.Mass / vol   ' kg/m^3
    m.EditRebuild3
    Set mp = m.Extension.CreateMassProperty
    got = mp.Mass
    If Abs(got - p.Mass) > 0.0005 * p.Mass Then
        ' a material from the template wins over the document density - override instead
        On Error Resume Next
        mp.OverrideMass = True
        mp.SetOverrideMassValue p.Mass
        On Error GoTo 0
        m.EditRebuild3
        Set mp = m.Extension.CreateMassProperty
        got = mp.Mass
    End If
    If Abs(got - p.Mass) > 0.0005 * p.Mass Then
        gLog = gLog & p.Name & ": mass is " & Format(got, "0.000") & " kg instead of " & p.Mass & _
               " kg - remove the material from the part template" & vbCrLf
    End If
    SetProp m, "Mass_kg", CStr(p.Mass)
End Sub

' Reference axis along X (Front x Top) named AXIS - used for the rotation mates
Private Sub AddAxis(ByVal m As SldWorks.ModelDoc2, planes() As SldWorks.Feature, ByVal partName As String)
    Dim f As SldWorks.Feature
    m.ClearSelection2 True
    planes(0).Select2 False, 0
    planes(1).Select2 True, 0
    If m.InsertAxis2(True) Then
        Set f = m.FeatureByPositionReverse(0)
        f.Name = AXIS_NAME
    Else
        gLog = gLog & partName & ": axis was not created - rotation mates will fail" & vbCrLf
    End If
    m.ClearSelection2 True
End Sub

' Interface: plane PORT_<name> at X + custom property PORT_<name> = "x=.. dir=.. key=value ..."
Private Sub AddPort(ByVal m As SldWorks.ModelDoc2, ByVal rightPlane As SldWorks.Feature, _
                    p As PartSpec, ByVal i As Long)
    Dim f As SldWorks.Feature, nm As String
    nm = "PORT_" & p.PortName(i)
    Set f = NewPlaneAtX(m, rightPlane, p.PortX(i))
    If f Is Nothing Then
        gLog = gLog & p.Name & ": interface plane " & nm & " was not created" & vbCrLf
    Else
        f.Name = nm
    End If
    SetProp m, nm, p.PortInfo(i)
End Sub

Private Sub SetProp(ByVal m As SldWorks.ModelDoc2, ByVal nm As String, ByVal v As String)
    Dim cpm As SldWorks.CustomPropertyManager, r As Long
    Set cpm = m.Extension.CustomPropertyManager("")
    On Error Resume Next
    r = cpm.Add3(nm, swCustomInfoText, v, swCustomPropertyReplaceValue)
    If Err.Number <> 0 Then
        Err.Clear
        r = cpm.Add2(nm, swCustomInfoText, v)
    End If
    If Err.Number <> 0 Then gLog = gLog & "Property " & nm & " was not written" & vbCrLf
    On Error GoTo 0
End Sub

' Feature of a part or component by name (FirstFeature -> GetNextFeature)
Private Function FindFeature(ByVal first As SldWorks.Feature, ByVal nm As String) As SldWorks.Feature
    Dim f As SldWorks.Feature
    Set f = first
    Do While Not f Is Nothing
        If StrComp(f.Name, nm, vbTextCompare) = 0 Then
            Set FindFeature = f
            Exit Function
        End If
        Set f = f.GetNextFeature
    Loop
End Function

' Tapped holes: tap-drill holes (Cut-Extrude, same as HOLES) + a cosmetic thread on
' every hole. Hole Wizard is not used: its API parameters are interpreted differently
' between versions and gave wrong geometry in SW 2017.
Private Sub AddThread(ByVal m As SldWorks.ModelDoc2, planes() As SldWorks.Feature, _
                      p As PartSpec, ByVal i As Long)
    Dim h As HoleSpec, idx As Long, k As Long, a As Double, r As Double
    Dim cut As SldWorks.Feature, nOk As Long, nominal As Double
    h = p.H(i)
    idx = i + 1

    ' 1. tap-drill holes
    Dim drill As HoleSpec
    drill = h
    drill.IsThread = False
    drill.Depth = h.DrillDepth
    AddHoles m, planes(2), drill, idx, p.Name
    Set cut = m.FeatureByPositionReverse(0)
    If cut.Name <> "Holes" & idx Then Exit Sub      ' cut failed, already logged
    cut.Name = "Thread" & idx & "_" & h.Size

    ' 2. cosmetic thread on the entry edges of the holes.
    ' Edge objects become invalid after every thread is added (the model rebuilds),
    ' so only the edge centres are kept; edges are re-picked by a ray when needed.
    Dim edges() As Object, cy() As Double, cz() As Double, nEdges As Long
    Dim why As String, missing As String, found As Boolean, j As Long
    Dim yc As Double, zc As Double, angDeg As Double
    nominal = Num(Mid(h.Size, 2))
    nEdges = EntryEdges(cut, h.X * MM, h.D / 2 * MM, edges, cy, cz)

    ' a) all found edges in one call
    If nEdges > 0 Then
        m.ClearSelection2 True
        For j = 0 To nEdges - 1
            edges(j).Select4 True, Nothing
        Next j
        If CosmeticThreadCall(m, nominal * MM, h.Depth * MM, h.Size, why) Then nOk = nEdges
        Erase edges                     ' do not touch them after the model changed
    End If

    ' b) every hole without a thread yet: re-pick its edge by a ray, one call per hole
    For k = 0 To h.N - 1
        angDeg = h.Ang + k * 360# / h.N
        a = angDeg * PI / 180#
        yc = h.Pcd / 2 * Sin(a) * MM
        zc = h.Pcd / 2 * Cos(a) * MM
        found = False
        If nOk > 0 Then
            For j = 0 To nEdges - 1
                If Abs(cy(j) - yc) < 0.00001 And Abs(cz(j) - zc) < 0.00001 Then found = True: Exit For
            Next j
        End If
        If Not found Then
            missing = missing & "    " & Format(angDeg, "0.##") & " deg: "
            If RayPickHoleEdge(m, h, a) Then
                why = ""
                If CosmeticThreadCall(m, nominal * MM, h.Depth * MM, h.Size, why) Then
                    nOk = nOk + 1
                    missing = missing & "ok" & vbCrLf
                Else
                    missing = missing & "edge picked, thread failed (" & why & ")" & vbCrLf
                End If
            Else
                missing = missing & "edge not picked by ray" & vbCrLf
            End If
        End If
    Next k
    m.ClearSelection2 True

    If nOk < h.N Then
        gLog = gLog & p.Name & ": " & h.Size & " (#" & idx & ") - cosmetic thread on " & nOk & _
               " of " & h.N & " holes (edges found: " & nEdges & ")" & vbCrLf & missing
    End If
End Sub

' Selects the entry edge of one hole with a ray along the drilling direction
Private Function RayPickHoleEdge(ByVal m As SldWorks.ModelDoc2, h As HoleSpec, ByVal a As Double) As Boolean
    Dim r As Double
    r = h.Pcd / 2 + h.D / 2                ' a point on the hole edge
    m.ClearSelection2 True
    RayPickHoleEdge = m.Extension.SelectByRay(h.X * MM - h.Dir * 0.0005, r * Sin(a) * MM, r * Cos(a) * MM, _
                                              h.Dir, 0, 0, 0.0002, swSelEDGES, False, 0, 0)
    If Not RayPickHoleEdge Then         ' fallback: the edge nearest to a point on it
        m.ClearSelection2 True
        RayPickHoleEdge = m.Extension.SelectByID2("", "EDGE", h.X * MM, r * Sin(a) * MM, r * Cos(a) * MM, _
                                                  False, 0, Nothing, 0)
    End If
End Function

' Circular edges of the cut lying in the plane X = x0 with the hole radius.
' Returns the edges and their centres (y, z).
Private Function EntryEdges(ByVal cut As SldWorks.Feature, ByVal x0 As Double, ByVal rad As Double, _
                            edges() As Object, cy() As Double, cz() As Double) As Long
    Dim faces As Variant, fe As Variant, eds As Variant, ed As Variant
    Dim c As SldWorks.Curve, cp As Variant, n As Long, k As Long, dup As Boolean
    ReDim edges(0 To 63): ReDim cy(0 To 63): ReDim cz(0 To 63)
    faces = cut.GetFaces
    If IsEmpty(faces) Then Exit Function
    For Each fe In faces
        eds = fe.GetEdges
        If Not IsEmpty(eds) Then
            For Each ed In eds
                Set c = ed.GetCurve
                If c.IsCircle Then
                    cp = c.CircleParams     ' center x,y,z, axis x,y,z, radius
                    If Abs(cp(0) - x0) < 0.00001 And Abs(cp(6) - rad) < 0.00001 Then
                        dup = False
                        For k = 0 To n - 1
                            If Abs(cy(k) - cp(1)) < 0.00001 And Abs(cz(k) - cp(2)) < 0.00001 Then dup = True: Exit For
                        Next k
                        If Not dup Then
                            If n > UBound(edges) Then
                                ReDim Preserve edges(0 To 2 * n)
                                ReDim Preserve cy(0 To 2 * n)
                                ReDim Preserve cz(0 To 2 * n)
                            End If
                            Set edges(n) = ed
                            cy(n) = cp(1): cz(n) = cp(2)
                            n = n + 1
                        End If
                    End If
                End If
            Next ed
        End If
    Next fe
    EntryEdges = n
End Function

Private Function CosmeticThreadCall(ByVal m As SldWorks.ModelDoc2, ByVal majorDia As Double, _
                                    ByVal length As Double, ByVal size As String, why As String) As Boolean
    Dim fm As Object, f As Object
    Set fm = m.FeatureManager
    On Error Resume Next
    ' InsertCosmeticThread3(Standard, Type, Size, Diameter, EndCondition, Length, Note)
    Set f = fm.InsertCosmeticThread3(-1, "", "", majorDia, 0, length, size)
    If Err.Number <> 0 Then why = "InsertCosmeticThread3: " & Err.Description
    If f Is Nothing Then
        Err.Clear
        ' older API: InsertCosmeticThread2(Type, Diameter, Length, Note)
        Set f = fm.InsertCosmeticThread2(0, majorDia, length, size)
        If Err.Number <> 0 Then why = why & "; InsertCosmeticThread2: " & Err.Description
    End If
    On Error GoTo 0
    If f Is Nothing And why = "" Then why = "API returned nothing"
    CosmeticThreadCall = Not (f Is Nothing)
End Function

' ---------------------------------------------------------------------------
' Prismatic parts (links): PRISM / CUT on planes normal to X, Y or Z, world frame
' ---------------------------------------------------------------------------
Private Function BuildPrismatic(ByVal m As SldWorks.ModelDoc2, planes() As SldWorks.Feature, _
                                p As PartSpec) As Boolean
    Dim i As Long, hasBody As Boolean, f As SldWorks.Feature
    For i = 0 To p.NOp - 1
        If p.OpKind(i) = 2 And Not hasBody Then
            gLog = gLog & p.Name & ": CUT #" & (i + 1) & " before any PRISM - skipped" & vbCrLf
        Else
            Set f = AddPrismOp(m, planes, p, i)
            If f Is Nothing Then
                If p.OpKind(i) = 1 And Not hasBody Then
                    gLog = gLog & p.Name & ": first PRISM failed" & vbCrLf
                    Exit Function
                End If
            ElseIf p.OpKind(i) = 1 Then
                hasBody = True
            End If
        End If
    Next i
    BuildPrismatic = hasBody
End Function

' Base plane of an axis: X -> Right (YZ), Y -> Top (XZ), Z -> Front (XY)
Private Function BasePlane(planes() As SldWorks.Feature, ByVal k As Integer) As SldWorks.Feature
    Select Case k
        Case 0: Set BasePlane = planes(2)
        Case 1: Set BasePlane = planes(1)
        Case Else: Set BasePlane = planes(0)
    End Select
End Function

' Model point (m) from the axis k, level along it and the plane coordinates (u, v), mm:
' X -> (level, u, v), Y -> (u, level, v), Z -> (u, v, level)
Private Function AxisPt(ByVal xf As SldWorks.MathTransform, ByVal k As Integer, ByVal lev As Double, _
                        ByVal u As Double, ByVal v As Double) As Variant
    Select Case k
        Case 0: AxisPt = ModelToSketch(xf, lev * MM, u * MM, v * MM)
        Case 1: AxisPt = ModelToSketch(xf, u * MM, lev * MM, v * MM)
        Case Else: AxisPt = ModelToSketch(xf, u * MM, v * MM, lev * MM)
    End Select
End Function

Private Function AddPrismOp(ByVal m As SldWorks.ModelDoc2, planes() As SldWorks.Feature, _
                            p As PartSpec, ByVal i As Long) As SldWorks.Feature
    Dim k As Integer, a0 As Double, a1 As Double, nm As String, pl As SldWorks.Feature
    Dim sm As SldWorks.SketchManager, xf As SldWorks.MathTransform, a() As String, nA As Long
    Dim j As Long, q0 As Variant, q1 As Variant, n As Long, t As Double, sk As SldWorks.Feature
    Dim f As Object, attempt As Long, rev As Boolean, dirSign As Integer
    k = p.OpAxis(i): a0 = p.OpA0(i): a1 = p.OpA1(i)
    nm = IIf(p.OpKind(i) = 1, "Prism", "Cut") & (i + 1)
    Set pl = GetPlaneK(m, BasePlane(planes, k), k, a0)
    If pl Is Nothing Then
        gLog = gLog & p.Name & ": cannot create plane " & Mid("XYZ", k + 1, 1) & "=" & a0 & " for " & nm & vbCrLf
        Exit Function
    End If
    a = Split(p.OpArgs(i), " ")
    nA = UBound(a) + 1
    Set sm = m.SketchManager
    m.ClearSelection2 True
    pl.Select2 False, 0
    sm.InsertSketch True
    Set xf = sm.ActiveSketch.ModelToSketchTransform
    SnapOff sm, True
    Select Case p.OpShape(i)
    Case "RECT"
        Dim uu(0 To 3) As Double, vv(0 To 3) As Double
        uu(0) = Num(a(0)): vv(0) = Num(a(2)): uu(1) = Num(a(1)): vv(1) = Num(a(2))
        uu(2) = Num(a(1)): vv(2) = Num(a(3)): uu(3) = Num(a(0)): vv(3) = Num(a(3))
        For j = 0 To 3
            q0 = AxisPt(xf, k, a0, uu(j), vv(j))
            q1 = AxisPt(xf, k, a0, uu((j + 1) Mod 4), vv((j + 1) Mod 4))
            sm.CreateLine q0(0), q0(1), 0, q1(0), q1(1), 0
        Next j
    Case "POLY"
        n = nA \ 2
        For j = 0 To n - 1
            q0 = AxisPt(xf, k, a0, Num(a(2 * j)), Num(a(2 * j + 1)))
            q1 = AxisPt(xf, k, a0, Num(a(2 * ((j + 1) Mod n))), Num(a(2 * ((j + 1) Mod n) + 1)))
            sm.CreateLine q0(0), q0(1), 0, q1(0), q1(1), 0
        Next j
    Case "RPOLY"
        SketchRPoly sm, xf, k, a0, a
    Case "CIRC", "RING"
        q0 = AxisPt(xf, k, a0, Num(a(0)), Num(a(1)))
        sm.CreateCircleByRadius q0(0), q0(1), 0, Num(a(2)) / 2 * MM
        If p.OpShape(i) = "RING" Then sm.CreateCircleByRadius q0(0), q0(1), 0, Num(a(3)) / 2 * MM
    Case "PATTERN"
        n = CLng(Num(a(2)))
        For j = 0 To n - 1
            t = (Num(a(5)) + j * 360# / n) * PI / 180#
            q0 = AxisPt(xf, k, a0, Num(a(0)) + Num(a(3)) / 2 * Cos(t), Num(a(1)) + Num(a(3)) / 2 * Sin(t))
            sm.CreateCircleByRadius q0(0), q0(1), 0, Num(a(4)) / 2 * MM
        Next j
    End Select
    SnapOff sm, False
    sm.InsertSketch True
    Set sk = m.FeatureByPositionReverse(0)
    sk.Name = nm & "_Sketch"

    dirSign = IIf(a1 > a0, 1, -1)
    For attempt = 0 To 1
        rev = (attempt = 1)
        m.ClearSelection2 True
        sk.Select2 False, 0
        Set f = Nothing
        On Error Resume Next
        If p.OpKind(i) = 1 Then
            Set f = m.FeatureManager.FeatureExtrusion2(True, False, rev, swEndCondBlind, swEndCondBlind, _
                        Abs(a1 - a0) * MM, 0, False, False, False, False, 0, 0, _
                        False, False, False, False, True, True, True, 0, 0, False)
        Else
            Set f = CutExtrude(m, True, rev, swEndCondBlind, Abs(a1 - a0) * MM)
        End If
        On Error GoTo 0
        If Not f Is Nothing Then
            If SideK(f, k, a0, dirSign) Then Exit For
            DeleteFeature m, f                        ' went to the wrong side of the sketch plane
            Set f = Nothing
        End If
    Next attempt
    If f Is Nothing Then
        gLog = gLog & p.Name & ": " & nm & " (" & p.OpShape(i) & " " & Mid("XYZ", k + 1, 1) & " " & a0 & ".." & a1 & _
               ") failed" & IIf(p.OpKind(i) = 2, " - nothing to cut?", "") & vbCrLf
        Exit Function
    End If
    f.Name = nm
    Set AddPrismOp = f
End Function

' Polygon with rounded corners: a = u1 v1 r1 u2 v2 r2 ... (r = 0 - sharp corner). Tangent points and
' centres are computed here; arcs are drawn as the minor arc between the tangent points.
Private Sub SketchRPoly(ByVal sm As SldWorks.SketchManager, ByVal xf As SldWorks.MathTransform, _
                        ByVal k As Integer, ByVal lev As Double, a() As String)
    Dim n As Long, i As Long, ia As Long, ib As Long
    Dim pu() As Double, pv() As Double, pr() As Double
    Dim t1u() As Double, t1v() As Double, t2u() As Double, t2v() As Double, cu() As Double, cv() As Double
    Dim u1u As Double, u1v As Double, u2u As Double, u2v As Double, l As Double, th As Double, tt As Double
    Dim bu As Double, bv As Double, q0 As Variant, q1 As Variant, qc As Variant, cr As Double
    n = (UBound(a) + 1) \ 3
    ReDim pu(0 To n - 1): ReDim pv(0 To n - 1): ReDim pr(0 To n - 1)
    ReDim t1u(0 To n - 1): ReDim t1v(0 To n - 1): ReDim t2u(0 To n - 1): ReDim t2v(0 To n - 1)
    ReDim cu(0 To n - 1): ReDim cv(0 To n - 1)
    For i = 0 To n - 1
        pu(i) = Num(a(3 * i)): pv(i) = Num(a(3 * i + 1)): pr(i) = Num(a(3 * i + 2))
    Next i
    For i = 0 To n - 1
        ia = (i + n - 1) Mod n: ib = (i + 1) Mod n
        t1u(i) = pu(i): t1v(i) = pv(i): t2u(i) = pu(i): t2v(i) = pv(i)
        If pr(i) > 0 Then
            u1u = pu(ia) - pu(i): u1v = pv(ia) - pv(i): l = Sqr(u1u ^ 2 + u1v ^ 2): u1u = u1u / l: u1v = u1v / l
            u2u = pu(ib) - pu(i): u2v = pv(ib) - pv(i): l = Sqr(u2u ^ 2 + u2v ^ 2): u2u = u2u / l: u2v = u2v / l
            th = u1u * u2u + u1v * u2v
            If th > 1 Then th = 1
            If th < -1 Then th = -1
            th = Atn(-th / Sqr(-th * th + 1 + 1E-15)) + 2 * Atn(1)      ' arccos
            tt = pr(i) / Tan(th / 2)
            t1u(i) = pu(i) + u1u * tt: t1v(i) = pv(i) + u1v * tt
            t2u(i) = pu(i) + u2u * tt: t2v(i) = pv(i) + u2v * tt
            bu = u1u + u2u: bv = u1v + u2v: l = Sqr(bu ^ 2 + bv ^ 2): bu = bu / l: bv = bv / l
            cu(i) = pu(i) + bu * pr(i) / Sin(th / 2): cv(i) = pv(i) + bv * pr(i) / Sin(th / 2)
        End If
    Next i
    For i = 0 To n - 1
        If pr(i) > 0 Then
            qc = AxisPt(xf, k, lev, cu(i), cv(i))
            q0 = AxisPt(xf, k, lev, t1u(i), t1v(i))
            q1 = AxisPt(xf, k, lev, t2u(i), t2v(i))
            cr = (q0(0) - qc(0)) * (q1(1) - qc(1)) - (q0(1) - qc(1)) * (q1(0) - qc(0))
            sm.CreateArc qc(0), qc(1), 0, q0(0), q0(1), 0, q1(0), q1(1), 0, IIf(cr > 0, 1, -1)
        End If
        ib = (i + 1) Mod n
        If Abs(t1u(ib) - t2u(i)) + Abs(t1v(ib) - t2v(i)) > 0.000001 Then
            q0 = AxisPt(xf, k, lev, t2u(i), t2v(i))
            q1 = AxisPt(xf, k, lev, t1u(ib), t1v(ib))
            sm.CreateLine q0(0), q0(1), 0, q1(0), q1(1), 0
        End If
    Next i
End Sub

' True if the faces of a feature reach beyond the sketch level on the side dirSign along axis k
Private Function SideK(ByVal feat As Object, ByVal k As Integer, ByVal lev As Double, ByVal dirSign As Integer) As Boolean
    Dim faces As Variant, fc As Variant, bx As Variant, lo As Double, hi As Double
    lo = 1E+30: hi = -1E+30
    faces = feat.GetFaces
    If IsEmpty(faces) Then SideK = True: Exit Function
    For Each fc In faces
        bx = fc.GetBox
        If bx(k) < lo Then lo = bx(k)
        If bx(k + 3) > hi Then hi = bx(k + 3)
    Next fc
    If dirSign > 0 Then
        SideK = (hi > lev * MM + 0.00001)
    Else
        SideK = (lo < lev * MM - 0.00001)
    End If
End Function

' Plane normal to axis k at the level (mm); reused by name "Plane_<axis><level>"
Private Function GetPlaneK(ByVal m As SldWorks.ModelDoc2, ByVal base As SldWorks.Feature, _
                           ByVal k As Integer, ByVal lev As Double) As SldWorks.Feature
    If Abs(lev) < 0.000001 Then
        Set GetPlaneK = base
        Exit Function
    End If
    Dim nm As String, pd As SldWorks.PartDoc, f As SldWorks.Feature
    nm = "Plane_" & Mid("XYZ", k + 1, 1) & Replace(CStr(lev), ",", ".")
    Set pd = m
    Set f = pd.FeatureByName(nm)
    If Not f Is Nothing Then
        Set GetPlaneK = f
        Exit Function
    End If
    Set f = NewPlaneK(m, base, k, lev)
    If f Is Nothing Then Exit Function
    f.Name = nm
    m.ClearSelection2 True
    f.Select2 False, 0
    m.BlankRefGeom
    m.ClearSelection2 True
    Set GetPlaneK = f
End Function

' New plane parallel to the base plane of axis k at the level (coincident when 0); side checked
Private Function NewPlaneK(ByVal m As SldWorks.ModelDoc2, ByVal base As SldWorks.Feature, _
                           ByVal k As Integer, ByVal lev As Double) As SldWorks.Feature
    Dim f As SldWorks.Feature, rp As SldWorks.RefPlane
    m.ClearSelection2 True
    base.Select2 False, 0
    If Abs(lev) < 0.000001 Then
        Set rp = m.FeatureManager.InsertRefPlane(swRefPlaneReferenceConstraint_Coincident, 0, 0, 0, 0, 0)
        If rp Is Nothing Then Exit Function
        Set NewPlaneK = m.FeatureByPositionReverse(0)
        m.ClearSelection2 True
        Exit Function
    End If
    Set rp = m.FeatureManager.InsertRefPlane(swRefPlaneReferenceConstraint_Distance, Abs(lev) * MM, 0, 0, 0, 0)
    If rp Is Nothing Then Exit Function
    Set f = m.FeatureByPositionReverse(0)
    If Sgn(PlaneCoord(rp, k)) <> Sgn(lev) Then
        m.ClearSelection2 True
        f.Select2 False, 0
        m.EditDelete
        m.ClearSelection2 True
        base.Select2 False, 0
        Set rp = m.FeatureManager.InsertRefPlane( _
            swRefPlaneReferenceConstraint_Distance + swRefPlaneReferenceConstraint_OptionFlip, _
            Abs(lev) * MM, 0, 0, 0, 0)
        If rp Is Nothing Then Exit Function
        Set f = m.FeatureByPositionReverse(0)
    End If
    m.ClearSelection2 True
    Set NewPlaneK = f
End Function

Private Function PlaneCoord(ByVal rp As SldWorks.RefPlane, ByVal k As Integer) As Double
    Dim t As SldWorks.MathTransform, v As Variant
    Set t = rp.Transform
    v = t.ArrayData
    PlaneCoord = v(9 + k)
End Function

' Interface plane of a prismatic part: PORT_<name> normal to the axis at the level + property
Private Sub AddPortP(ByVal m As SldWorks.ModelDoc2, planes() As SldWorks.Feature, _
                     p As PartSpec, ByVal i As Long)
    Dim f As SldWorks.Feature, nm As String, k As Integer
    nm = "PORT_" & p.PortName(i)
    k = p.PortAxis(i)
    Set f = NewPlaneK(m, BasePlane(planes, k), k, p.PortX(i))
    If f Is Nothing Then
        gLog = gLog & p.Name & ": interface plane " & nm & " was not created" & vbCrLf
    Else
        f.Name = nm
    End If
    SetProp m, nm, p.PortInfo(i)
End Sub

Private Function ModelToSketch(ByVal xf As SldWorks.MathTransform, ByVal x As Double, _
                               ByVal y As Double, ByVal z As Double) As Variant
    Dim mu As SldWorks.MathUtility, mp As SldWorks.MathPoint, pt(2) As Double
    pt(0) = x: pt(1) = y: pt(2) = z
    Set mu = swApp.GetMathUtility
    Set mp = mu.CreatePoint(pt)
    Set mp = mp.MultiplyTransform(xf)
    ModelToSketch = mp.ArrayData
End Function

' Tap drill diameter for ISO coarse metric threads, mm (0 = unknown size)
Private Function TapDrill(ByVal size As String) As Double
    Select Case UCase(Trim(size))
        Case "M1.6": TapDrill = 1.25
        Case "M2": TapDrill = 1.6
        Case "M2.5": TapDrill = 2.05
        Case "M3": TapDrill = 2.5
        Case "M4": TapDrill = 3.3
        Case "M5": TapDrill = 4.2
        Case "M6": TapDrill = 5
        Case "M8": TapDrill = 6.8
        Case "M10": TapDrill = 8.5
        Case "M12": TapDrill = 10.2
        Case "M14": TapDrill = 12
        Case "M16": TapDrill = 14
        Case "M20": TapDrill = 17.5
        Case Else: TapDrill = 0
    End Select
End Function

Private Function PlaneX(ByVal rp As SldWorks.RefPlane) As Double
    Dim t As SldWorks.MathTransform, v As Variant
    Set t = rp.Transform
    v = t.ArrayData
    PlaneX = v(9)
End Function

' First three reference planes (Front, Top, Right) - independent of UI language
Private Function GetRefPlanes(ByVal first As SldWorks.Feature, planes() As SldWorks.Feature) As Boolean
    Dim f As SldWorks.Feature, k As Long
    Set f = first
    Do While Not f Is Nothing
        If f.GetTypeName2 = "RefPlane" Then
            Set planes(k) = f
            k = k + 1
            If k = 3 Then
                GetRefPlanes = True
                Exit Function
            End If
        End If
        Set f = f.GetNextFeature
    Loop
End Function

' ---------------------------------------------------------------------------
' Assembly
' ---------------------------------------------------------------------------
Private Sub BuildAssembly(ByVal asmPath As String, partPaths() As String, ByVal keepOpen As Boolean)
    Dim am As SldWorks.ModelDoc2, asm As SldWorks.AssemblyDoc
    If gTplAsm = "" Then gTplAsm = FindTemplate("asmdot", swDefaultTemplateAssembly, "assem")
    If gTplAsm <> "" Then Set am = swApp.NewDocument(gTplAsm, 0, 0, 0)
    If am Is Nothing Then
        gLog = gLog & "Cannot create an assembly from the template:" & vbCrLf & "  '" & gTplAsm & "'" & vbCrLf & _
               "Set it in Options - Default Templates (Assembly) or pick a *.asmdot when asked." & vbCrLf
        Exit Sub
    End If
    Set asm = am

    Dim asmPlanes(0 To 2) As SldWorks.Feature, cp(0 To 2) As SldWorks.Feature
    If Not GetRefPlanes(am.FirstFeature, asmPlanes) Then
        gLog = gLog & "Reference planes not found in the assembly template." & vbCrLf
        Exit Sub
    End If

    ' 1. insert all parts (floating)
    Dim i As Long, k As Long, baseIdx As Long
    Dim comps() As SldWorks.Component2
    ReDim comps(LBound(partPaths) To UBound(partPaths))
    For i = LBound(partPaths) To UBound(partPaths)
        LoadHidden partPaths(i)
        Set comps(i) = asm.AddComponent5(partPaths(i), swAddComponentConfigOptions_CurrentSelectedConfig, _
                                         "", False, "", 0, 0, 0)
        If comps(i) Is Nothing Then
            gLog = gLog & "Cannot insert " & partPaths(i) & vbCrLf
        Else
            am.ClearSelection2 True
            comps(i).Select4 False, Nothing, False
            asm.UnfixComponent
        End If
    Next i

    ' 2. fixed parts: 3 coincident mates to the assembly planes
    baseIdx = -1
    For i = LBound(partPaths) To UBound(partPaths)
        If Not comps(i) Is Nothing And gParts(i).Motion = 0 Then
            If baseIdx < 0 Then baseIdx = i
            If GetRefPlanes(comps(i).FirstFeature, cp) Then
                For k = 0 To 2
                    MatePair am, asm, asmPlanes(k), cp(k), swMateCOINCIDENT, comps(i).Name2 & ": mate " & (k + 1)
                Next k
            Else
                gLog = gLog & comps(i).Name2 & ": planes not found, component left floating" & vbCrLf
            End If
        End If
    Next i

    ' 3. rotating parts: axis on the AXIS of the first fixed part + Right plane on Right plane
    Dim ax As SldWorks.Feature, baseAx As SldWorks.Feature, mate As Object
    If baseIdx >= 0 Then Set baseAx = FindFeature(comps(baseIdx).FirstFeature, AXIS_NAME)
    For i = LBound(partPaths) To UBound(partPaths)
        If Not comps(i) Is Nothing And gParts(i).Motion = 1 Then
            Set ax = FindFeature(comps(i).FirstFeature, AXIS_NAME)
            If baseAx Is Nothing Or ax Is Nothing Then
                gLog = gLog & comps(i).Name2 & ": no fixed part or no AXIS - rotation mates not added" & vbCrLf
            Else
                Set mate = MatePair(am, asm, baseAx, ax, swMateCOINCIDENT, "")
                If mate Is Nothing Then Set mate = MatePair(am, asm, baseAx, ax, swMateCONCENTRIC, _
                                                            comps(i).Name2 & ": axis mate")
                If Not mate Is Nothing Then NameMate mate, "Rot_" & gParts(i).Name & "_Axis"
                If GetRefPlanes(comps(i).FirstFeature, cp) Then
                    Set mate = MatePair(am, asm, asmPlanes(2), cp(2), swMateCOINCIDENT, _
                                        comps(i).Name2 & ": axial mate")
                    If Not mate Is Nothing Then NameMate mate, "Rot_" & gParts(i).Name & "_Axial"
                End If
            End If
        End If
    Next i

    ' 4. catalog data -> custom properties of the assembly
    Dim kv As Variant, eq As Long
    For Each kv In Split(Trim(gData), " ")
        eq = InStr(kv, "=")
        If eq > 1 Then SetProp am, Left(kv, eq - 1), Mid(kv, eq + 1)
    Next kv

    am.ClearSelection2 True
    am.EditRebuild3
    am.ShowNamedView2 "*Isometric", swIsometricView
    am.ViewZoomtofit2

    If SaveDoc(am, asmPath) And Not keepOpen Then
        CloseSaved am, False
        CloseHidden
    End If
End Sub

Private Sub NameMate(ByVal mate As Object, ByVal nm As String)
    On Error Resume Next        ' a name is only a convenience
    mate.Name = nm
    On Error GoTo 0
End Sub

' Mate of two selected entities (ALIGNED). Logs a failure only when errName is given.
Private Function MatePair(ByVal am As SldWorks.ModelDoc2, ByVal asm As SldWorks.AssemblyDoc, _
                          ByVal a As SldWorks.Feature, ByVal b As SldWorks.Feature, _
                          ByVal mateType As Long, ByVal errName As String) As Object
    Dim errStat As Long
    am.ClearSelection2 True
    a.Select2 False, 1
    b.Select2 True, 1
    Set MatePair = asm.AddMate3(mateType, swMateAlignALIGNED, False, _
                                0, 0, 0, 0, 0, 0, 0, 0, False, errStat)
    If MatePair Is Nothing And errName <> "" Then
        gLog = gLog & errName & " failed (status " & errStat & ")" & vbCrLf
    End If
    am.ClearSelection2 True
End Function

' ---------------------------------------------------------------------------
' Joint: sub-assemblies / imported components / designed parts in one assembly
' ---------------------------------------------------------------------------
Private Function BuildJoint(ByVal jointPath As String) As Boolean
    Dim lines() As String, li As Long, s As String, t() As String, folder As String
    Dim jName As String, partsFile As String
    Dim uRole(0 To 15) As String, uFile(0 To 15) As String, uModel(0 To 15) As String
    Dim uIsAsm(0 To 15) As Boolean, uPlaced(0 To 15) As Boolean, uX(0 To 15) As Double, uFlip(0 To 15) As Boolean
    Dim nU As Long, k As Long, i As Long
    Dim lnkPart(0 To 15) As String, lnkTo(0 To 15) As String, nL As Long

    folder = Left(jointPath, InStrRev(jointPath, "\"))
    lines = ReadLines(jointPath)
    For li = LBound(lines) To UBound(lines)
        s = CleanLine(lines(li))
        If s <> "" Then
            t = Split(s, " ")
            Select Case UCase(t(0))
            Case "JOINT"
                jName = t(1)
            Case "USE"
                If UBound(t) >= 3 Then
                    If t(2) <> "?" And nU <= 15 Then
                        uRole(nU) = t(1)
                        uFile(nU) = ResolvePath(folder, t(3))
                        If uFile(nU) = "" Then
                            gLog = gLog & "USE " & t(1) & ": file not found: " & t(3) & vbCrLf
                            Exit Function
                        End If
                        nU = nU + 1
                    End If
                End If
            Case "PARTS"
                If UBound(t) < 1 Then gLog = gLog & "PARTS needs a file" & vbCrLf: Exit Function
                partsFile = ResolvePath(folder, t(1))
                If partsFile = "" Then
                    gLog = gLog & "PARTS: file not found: " & t(1) & vbCrLf
                    Exit Function
                End If
            Case "PLACE"
                If UBound(t) < 2 Then gLog = gLog & "PLACE needs <role> <x>" & vbCrLf: Exit Function
                For k = 0 To nU - 1
                    If uRole(k) = t(1) Then
                        uPlaced(k) = True
                        uX(k) = Num(t(2))
                        If UBound(t) >= 3 Then uFlip(k) = (LCase(t(3)) = "flip")
                    End If
                Next k
            Case "LINK"
                If UBound(t) < 2 Then gLog = gLog & "LINK needs <part> <child part>" & vbCrLf: Exit Function
                If nL <= 15 Then lnkPart(nL) = t(1): lnkTo(nL) = t(2): nL = nL + 1
            End Select
        End If
    Next li
    If jName = "" Or nU = 0 Then
        gLog = gLog & "JOINT file needs JOINT <name> and at least one USE line." & vbCrLf
        Exit Function
    End If

    ' 1. components: specs are built, cards with STEP / BODY are imported;
    '    every model becomes an entry (a card with BODY lines gives several)
    Dim eModel(0 To 31) As String, eName(0 To 31) As String, eIsAsm(0 To 31) As Boolean
    Dim ePlaced(0 To 31) As Boolean, eX(0 To 31) As Double, eFlip(0 To 31) As Boolean, nE As Long
    Dim mp() As String, q As Long
    For k = 0 To nU - 1
        If FileHasKeyword(uFile(k), "PART") Then
            ' v30: a component (reducer) built before is reused - rebuilding it here re-saves its parts over the
            ' files other models in memory refer to (their mates then break); REBUILD yes of an arm rebuilds it
            uModel(k) = ""
            If FirstArg(uFile(k), "ASSEMBLY") <> "" And Not gRebuildAll Then
                uModel(k) = Left(uFile(k), InStrRev(uFile(k), "\")) & FirstArg(uFile(k), "ASSEMBLY") & ".SLDASM"
                If Not FileExists(uModel(k)) Then uModel(k) = ""
            End If
            If uModel(k) <> "" Then
                gSummary = gSummary & Mid(uModel(k), InStrRev(uModel(k), "\") + 1) & ": built before, reused" & vbCrLf
            ElseIf Not BuildSpecFile(uFile(k), uModel(k)) Then
                Exit Function
            End If
            If uModel(k) = "" Then
                gLog = gLog & uRole(k) & ": the spec has no ASSEMBLY line" & vbCrLf
                Exit Function
            End If
            uIsAsm(k) = True
        ElseIf FileHasKeyword(uFile(k), "STEP") Or FileHasKeyword(uFile(k), "BODY") Then
            uModel(k) = ImportCard(uFile(k))
            If uModel(k) = "" Then Exit Function
            gSummary = gSummary & Mid(uFile(k), InStrRev(uFile(k), "\") + 1) & ": STEP imported" & vbCrLf
        Else
            gLog = gLog & uRole(k) & ": neither PARTs nor STEP in " & uFile(k) & vbCrLf
            Exit Function
        End If
        mp = Split(uModel(k), "|")
        For q = 0 To UBound(mp)
            If nE <= 31 Then
                eModel(nE) = mp(q)
                eName(nE) = Mid(mp(q), InStrRev(mp(q), "\") + 1)
                eName(nE) = Left(eName(nE), InStrRev(eName(nE), ".") - 1)
                eIsAsm(nE) = uIsAsm(k): ePlaced(nE) = uPlaced(k): eX(nE) = uX(k): eFlip(nE) = uFlip(k)
                nE = nE + 1
            End If
        Next q
    Next k

    ' 2. designed parts (they stay in gParts / gPartPaths)
    Dim dummy As String, nD As Long
    If partsFile <> "" Then
        If Not BuildSpecFile(partsFile, dummy) Then Exit Function
        nD = gNParts
    End If

    ' 3. the joint assembly
    Dim am As SldWorks.ModelDoc2, asm As SldWorks.AssemblyDoc
    If gTplAsm = "" Then gTplAsm = FindTemplate("asmdot", swDefaultTemplateAssembly, "assem")
    If gTplAsm <> "" Then Set am = swApp.NewDocument(gTplAsm, 0, 0, 0)
    If am Is Nothing Then
        gLog = gLog & "Cannot create the joint assembly from '" & gTplAsm & "'" & vbCrLf
        Exit Function
    End If
    Set asm = am
    Dim asmPlanes(0 To 2) As SldWorks.Feature, cp(0 To 2) As SldWorks.Feature
    If Not GetRefPlanes(am.FirstFeature, asmPlanes) Then
        gLog = gLog & "Reference planes not found in the assembly template." & vbCrLf
        Exit Function
    End If

    ' sub-assemblies first (the LINK targets are inside them), then the other entries
    Dim eComp(0 To 31) As SldWorks.Component2, co As Object, pass As Long, tgt As String, jj As Long
    Dim dc As SldWorks.Component2, child As SldWorks.Component2, target As String, j As Long
    For pass = 0 To 1
        For k = 0 To nE - 1
            If eIsAsm(k) = (pass = 0) Then
                Set eComp(k) = InsertFloating(am, asm, eModel(k))
                If eComp(k) Is Nothing Then Exit Function
                If eIsAsm(k) Then
                    Set co = eComp(k)
                    On Error Resume Next
                    co.Solving = 1                 ' flexible: the shafts of the sub-assembly can turn
                    On Error GoTo 0
                End If
                tgt = ""
                For jj = 0 To nL - 1
                    If StrComp(lnkPart(jj), eName(k), vbTextCompare) = 0 Then tgt = lnkTo(jj)
                Next jj
                If tgt <> "" Then
                    ' imported body moving with a part of a sub-assembly: placed, then locked to it
                    PlaceComp eComp(k), eX(k), eFlip(k), ePlaced(k)
                    Set child = Nothing
                    For jj = 0 To nE - 1
                        If eIsAsm(jj) And child Is Nothing And Not eComp(jj) Is Nothing Then
                            Set child = FindChild(eComp(jj), tgt)
                        End If
                    Next jj
                    If child Is Nothing Then
                        gLog = gLog & "LINK " & eName(k) & ": part '" & tgt & "' not found - fixed instead" & vbCrLf
                        FixComp am, asm, eComp(k)
                    ElseIf MateLock(am, asm, child, eComp(k)) Is Nothing Then
                        gLog = gLog & "LINK " & eName(k) & ": lock mate failed - fixed instead" & vbCrLf
                        FixComp am, asm, eComp(k)
                    End If
                ElseIf ePlaced(k) Then
                    PlaceComp eComp(k), eX(k), eFlip(k), True
                    FixComp am, asm, eComp(k)
                Else
                    MateToPlanes am, asm, eComp(k), asmPlanes
                End If
            End If
        Next k
    Next pass

    For i = 0 To nD - 1
        Set dc = InsertFloating(am, asm, gPartPaths(i))
        If dc Is Nothing Then Exit Function
        target = ""
        For j = 0 To nL - 1
            If StrComp(lnkPart(j), gParts(i).Name, vbTextCompare) = 0 Then target = lnkTo(j)
        Next j
        If target = "" Then
            MateToPlanes am, asm, dc, asmPlanes
        Else
            Set child = Nothing
            For k = 0 To nE - 1
                If eIsAsm(k) And child Is Nothing Then Set child = FindChild(eComp(k), target)
            Next k
            If child Is Nothing Then
                gLog = gLog & "LINK " & gParts(i).Name & ": part '" & target & "' not found - fixed instead" & vbCrLf
                MateToPlanes am, asm, dc, asmPlanes
            ElseIf GetRefPlanes(child.FirstFeature, cp) Then
                For j = 0 To 2
                    MatePair am, asm, cp(j), FirstPlanes(dc, j), swMateCOINCIDENT, _
                             dc.Name2 & ": link mate " & (j + 1)
                Next j
            End If
        End If
    Next i

    am.ClearSelection2 True
    am.EditRebuild3
    am.ShowNamedView2 "*Isometric", swIsometricView
    am.ViewZoomtofit2
    If Not SaveDoc(am, folder & jName & ".SLDASM") Then Exit Function
    If Not IsTopSpec(jointPath) Then
        CloseSaved am, False
        CloseHidden
    End If
    gSummary = gSummary & "joint " & jName & ": " & nE & " component(s) + " & nD & " designed part(s)" & vbCrLf
    BuildJoint = True
End Function

' ---------------------------------------------------------------------------
' Arm assembly: built models placed by a frame (origin + X and Z directions), fixed
' ---------------------------------------------------------------------------
Private Function BuildRobotAsm(ByVal specPath As String) As Boolean
    Dim lines() As String, li As Long, s As String, t() As String, folder As String
    Dim aName As String, rebuild As Boolean, k As Long, q As Long
    Dim cName(0 To 63) As String, cFile(0 To 63) As String, cFr(0 To 63, 0 To 8) As Double, nC As Long
    Dim cRigid(0 To 63) As Boolean, lk(0 To 63, 0 To 3) As String, nLk As Long, lkKeep(0 To 63) As Boolean
    Dim cRebuild(0 To 63) As Boolean
    folder = Left(specPath, InStrRev(specPath, "\"))
    lines = ReadLines(specPath)
    For li = LBound(lines) To UBound(lines)
        s = CleanLine(lines(li))
        If s <> "" Then
            t = Split(s, " ")
            Select Case UCase(t(0))
            Case "ROBOTASM"
                aName = t(1)
            Case "REBUILD"
                rebuild = (LCase(t(1)) = "yes")
                gRebuildAll = rebuild
            Case "COMP"
                If UBound(t) < 11 Then gLog = gLog & "COMP needs: name file ox oy oz xx xy xz zx zy zz" & vbCrLf: Exit Function
                If nC > 63 Then gLog = gLog & "too many COMP lines" & vbCrLf: Exit Function
                cName(nC) = t(1)
                cFile(nC) = ResolvePath(folder, t(2))
                If cFile(nC) = "" Then gLog = gLog & "COMP " & t(1) & ": file not found: " & t(2) & vbCrLf: Exit Function
                For q = 0 To 8
                    cFr(nC, q) = Num(t(3 + q))
                Next q
                For q = 12 To UBound(t)
                    If LCase(t(q)) = "rigid" Then cRigid(nC) = True
                    If LCase(t(q)) = "rebuild" Then cRebuild(nC) = True   ' v29: rebuild this model even if it exists
                Next q
                nC = nC + 1
            Case "LOCK"
                If UBound(t) < 4 Then gLog = gLog & "LOCK needs: comp part comp part" & vbCrLf: Exit Function
                If nLk <= 63 Then
                    For q = 0 To 3
                        lk(nLk, q) = t(1 + q)
                    Next q
                    If UBound(t) >= 5 Then lkKeep(nLk) = (LCase(t(5)) = "keep")
                    nLk = nLk + 1
                End If
            End Select
        End If
    Next li
    If aName = "" Or nC = 0 Then gLog = gLog & "ROBOTASM file needs ROBOTASM <name> and COMP lines" & vbCrLf: Exit Function

    ' 1. models (each spec file built once)
    Dim cModel(0 To 63) As String, ext As String, jn As String, asmPath As String, j As Long
    For k = 0 To nC - 1
        For j = 0 To k - 1
            If StrComp(cFile(j), cFile(k), vbTextCompare) = 0 Then cModel(k) = cModel(j)
        Next j
        If cModel(k) = "" Then
            ext = UCase(Mid(cFile(k), InStrRev(cFile(k), ".") + 1))
            If ext = "SLDASM" Or ext = "SLDPRT" Then
                cModel(k) = cFile(k)
            ElseIf FileHasKeyword(cFile(k), "JOINT") Then
                jn = FirstArg(cFile(k), "JOINT")
                cModel(k) = Left(cFile(k), InStrRev(cFile(k), "\")) & jn & ".SLDASM"
                If rebuild Or cRebuild(k) Or Not FileExists(cModel(k)) Then
                    If Not BuildJoint(cFile(k)) Then Exit Function
                End If
            Else
                jn = FirstArg(cFile(k), "ASSEMBLY")
                If jn = "" Then gLog = gLog & "COMP " & cName(k) & ": the spec has no ASSEMBLY line" & vbCrLf: Exit Function
                cModel(k) = Left(cFile(k), InStrRev(cFile(k), "\")) & jn & ".SLDASM"
                If rebuild Or cRebuild(k) Or Not FileExists(cModel(k)) Then
                    If Not BuildSpecFile(cFile(k), asmPath) Then Exit Function
                End If
            End If
        End If
    Next k

    ' 2. the arm assembly
    Dim am As SldWorks.ModelDoc2, asm As SldWorks.AssemblyDoc, c As SldWorks.Component2
    If gTplAsm = "" Then gTplAsm = FindTemplate("asmdot", swDefaultTemplateAssembly, "assem")
    If gTplAsm <> "" Then Set am = swApp.NewDocument(gTplAsm, 0, 0, 0)
    If am Is Nothing Then gLog = gLog & "Cannot create the assembly from '" & gTplAsm & "'" & vbCrLf: Exit Function
    Set asm = am
    Dim errs As Long, warns As Long, d As Object, comps(0 To 63) As SldWorks.Component2
    For k = 0 To nC - 1
        ' the model must be open for AddComponent5
        LoadHidden cModel(k)                    ' no window (CLOSE_DOCS), active document stays the assembly
        swApp.ActivateDoc3 am.GetTitle, False, swDontRebuildActiveDoc, errs
        Set c = InsertFloating(am, asm, cModel(k))
        If c Is Nothing Then Exit Function
        If UCase(Right(cModel(k), 6)) = "SLDASM" And Not cRigid(k) Then
            On Error Resume Next
            Dim co As Object
            Set co = c
            co.Solving = 1                          ' flexible: the shafts inside can turn
            On Error GoTo 0
        End If
        PlaceFrame c, cFr, k
        FixComp am, asm, c
        Set comps(k) = c
        gSummary = gSummary & "  " & cName(k) & ": " & Mid(cModel(k), InStrRev(cModel(k), "\") + 1) & vbCrLf
    Next k
    ' 3. degrees of freedom: LOCK lines replace the fixing of the first component
    Dim ia As Long, ib As Long, pa As SldWorks.Component2, pb As SldWorks.Component2, nOk As Long
    For q = 0 To nLk - 1
        ia = -1: ib = -1
        For k = 0 To nC - 1
            If StrComp(cName(k), lk(q, 0), vbTextCompare) = 0 Then ia = k
            If StrComp(cName(k), lk(q, 2), vbTextCompare) = 0 Then ib = k
        Next k
        If ia < 0 Or ib < 0 Then
            gLog = gLog & "LOCK " & lk(q, 0) & " -> " & lk(q, 2) & ": component not found" & vbCrLf
        Else
            If lk(q, 1) = "-" Then Set pa = comps(ia) Else Set pa = FindDeep(comps(ia), lk(q, 1))
            If lk(q, 3) = "-" Then Set pb = comps(ib) Else Set pb = FindDeep(comps(ib), lk(q, 3))
            If pa Is Nothing Or pb Is Nothing Then
                gLog = gLog & "LOCK " & lk(q, 0) & ": part " & IIf(pa Is Nothing, lk(q, 1), lk(q, 3)) & " not found - stays fixed" & vbCrLf
            Else
                If Not lkKeep(q) Then
                    am.ClearSelection2 True
                    comps(ia).Select4 False, Nothing, False
                    asm.UnfixComponent
                    am.ClearSelection2 True
                End If
                If MateLock(am, asm, pa, pb) Is Nothing Then
                    gLog = gLog & "LOCK " & lk(q, 0) & " -> " & lk(q, 2) & ": lock mate failed - fixed again" & vbCrLf
                    FixComp am, asm, comps(ia)
                Else
                    nOk = nOk + 1
                End If
            End If
        End If
    Next q

    am.ClearSelection2 True
    am.EditRebuild3
    am.ShowNamedView2 "*Isometric", swIsometricView
    am.ViewZoomtofit2
    If Not SaveDoc(am, folder & aName & ".SLDASM") Then Exit Function
    If nLk > 0 Then gSummary = "lock mates: " & nOk & " of " & nLk & vbCrLf & gSummary
    gSummary = "arm assembly " & aName & ": " & nC & " component(s)" & vbCrLf & gSummary
    BuildRobotAsm = True
End Function

' ---------------------------------------------------------------- animation of the arm (ROBOTANIM)
' Model (.SLDASM / .SLDPRT) of a COMP file: built when missing (or REBUILD yes), "" on failure
Private Function ModelOfComp(ByVal f As String, ByVal rebuild As Boolean, ByVal cn As String) As String
    Dim ext As String, jn As String, m As String, asmPath As String
    ext = UCase(Mid(f, InStrRev(f, ".") + 1))
    If ext = "SLDASM" Or ext = "SLDPRT" Then ModelOfComp = f: Exit Function
    If FileHasKeyword(f, "JOINT") Then
        jn = FirstArg(f, "JOINT")
        m = Left(f, InStrRev(f, "\")) & jn & ".SLDASM"
        If rebuild Or Not FileExists(m) Then
            If Not BuildJoint(f) Then Exit Function
        End If
    Else
        jn = FirstArg(f, "ASSEMBLY")
        If jn = "" Then gLog = gLog & "COMP " & cn & ": the spec has no ASSEMBLY line" & vbCrLf: Exit Function
        m = Left(f, InStrRev(f, "\")) & jn & ".SLDASM"
        If rebuild Or Not FileExists(m) Then
            If Not BuildSpecFile(f, asmPath) Then Exit Function
        End If
    End If
    ModelOfComp = m
End Function

Private Function BuildRobotAnim(ByVal specPath As String) As Boolean
    Dim lines() As String, li As Long, s As String, t() As String, folder As String
    Dim aName As String, rebuild As Boolean, k As Long, q As Long, j As Long
    Dim cName(0 To 63) As String, cFile(0 To 63) As String, cFr(0 To 63, 0 To 8) As Double, nC As Long
    Dim imgExt As String, viewName As String, zoomK As Double, r0 As Long, r1 As Long
    Dim fr() As Double, nF As Long, curF As Long
    folder = Left(specPath, InStrRev(specPath, "\"))
    lines = ReadLines(specPath)
    imgExt = "jpg": viewName = "*Isometric": zoomK = 0.8: r0 = 0: r1 = -1
    ' pass 1: header, components, number of frames
    For li = LBound(lines) To UBound(lines)
        s = CleanLine(lines(li))
        If s <> "" Then
            t = Split(s, " ")
            Select Case UCase(t(0))
            Case "ROBOTANIM": aName = t(1)
            Case "REBUILD": rebuild = (LCase(t(1)) = "yes")
            Case "IMAGES": imgExt = LCase(t(1))
            Case "VIEW": viewName = t(1)
            Case "ZOOM": zoomK = Num(t(1))
            Case "RANGE": r0 = CLng(t(1)): r1 = CLng(t(2))
            Case "COMP"
                If UBound(t) < 11 Or nC > 63 Then gLog = gLog & "bad COMP line: " & s & vbCrLf: Exit Function
                cName(nC) = t(1)
                cFile(nC) = ResolvePath(folder, t(2))
                If cFile(nC) = "" Then gLog = gLog & "COMP " & t(1) & ": file not found: " & t(2) & vbCrLf: Exit Function
                For q = 0 To 8: cFr(nC, q) = Num(t(3 + q)): Next q
                nC = nC + 1
            Case "FRAME": nF = nF + 1
            End Select
        End If
    Next li
    If aName = "" Or nC = 0 Or nF = 0 Then gLog = gLog & "ROBOTANIM file needs ROBOTANIM <name>, COMP and FRAME lines" & vbCrLf: Exit Function
    ReDim fr(0 To nF * nC - 1, 0 To 8)
    For k = 0 To nF - 1          ' a component without a P line in a frame stays at its COMP frame
        For j = 0 To nC - 1
            For q = 0 To 8: fr(k * nC + j, q) = cFr(j, q): Next q
        Next j
    Next k
    ' pass 2: P lines
    curF = -1
    For li = LBound(lines) To UBound(lines)
        s = CleanLine(lines(li))
        If s <> "" Then
            t = Split(s, " ")
            If UCase(t(0)) = "FRAME" Then
                curF = curF + 1
            ElseIf UCase(t(0)) = "P" And curF >= 0 And UBound(t) >= 10 Then
                For j = 0 To nC - 1
                    If StrComp(cName(j), t(1), vbTextCompare) = 0 Then
                        For q = 0 To 8: fr(curF * nC + j, q) = Num(t(2 + q)): Next q
                    End If
                Next j
            End If
        End If
    Next li
    If r1 < 0 Or r1 > nF - 1 Then r1 = nF - 1
    If r0 < 0 Then r0 = 0

    ' models + assembly without mates (components floating, sub-assemblies rigid)
    Dim cModel(0 To 63) As String
    For k = 0 To nC - 1
        For j = 0 To k - 1
            If StrComp(cFile(j), cFile(k), vbTextCompare) = 0 Then cModel(k) = cModel(j)
        Next j
        If cModel(k) = "" Then cModel(k) = ModelOfComp(cFile(k), rebuild, cName(k))
        If cModel(k) = "" Then Exit Function
    Next k
    Dim am As SldWorks.ModelDoc2, asm As SldWorks.AssemblyDoc, c As SldWorks.Component2
    Dim errs As Long, warns As Long, d As Object, comps(0 To 63) As SldWorks.Component2
    If gTplAsm = "" Then gTplAsm = FindTemplate("asmdot", swDefaultTemplateAssembly, "assem")
    If gTplAsm <> "" Then Set am = swApp.NewDocument(gTplAsm, 0, 0, 0)
    If am Is Nothing Then gLog = gLog & "Cannot create the assembly from '" & gTplAsm & "'" & vbCrLf: Exit Function
    Set asm = am
    For k = 0 To nC - 1
        LoadHidden cModel(k)                    ' no window (CLOSE_DOCS), active document stays the assembly
        swApp.ActivateDoc3 am.GetTitle, False, swDontRebuildActiveDoc, errs
        Set c = InsertFloating(am, asm, cModel(k))
        If c Is Nothing Then Exit Function
        Set comps(k) = c
    Next k
    Dim one(0 To 0, 0 To 8) As Double
    For k = 0 To nC - 1
        For q = 0 To 8: one(0, q) = fr(r0 * nC + k, q): Next q
        PlaceFrame comps(k), one, 0
    Next k
    am.ClearSelection2 True
    am.EditRebuild3
    am.ShowNamedView2 viewName, -1
    am.ViewZoomtofit2
    On Error Resume Next
    Dim mv As Object
    Set mv = am.ActiveView
    mv.Scale2 = mv.Scale2 * zoomK          ' room for the stretched poses
    On Error GoTo 0
    If Not SaveDoc(am, folder & aName & ".SLDASM") Then Exit Function

    ' frames
    Dim outDir As String, nImg As Long, fpath As String, t0 As Double
    If imgExt <> "none" Then
        outDir = folder & aName & "-frames\"
        If Dir(outDir, vbDirectory) = "" Then MkDir outDir
    End If
    t0 = Timer
    For k = r0 To r1
        For j = 0 To nC - 1
            For q = 0 To 8: one(0, q) = fr(k * nC + j, q): Next q
            PlaceFrame comps(j), one, 0
        Next j
        am.GraphicsRedraw2
        DoEvents
        If imgExt <> "none" Then
            fpath = outDir & "f" & Format(k - r0, "0000") & "." & imgExt
            If am.Extension.SaveAs(fpath, swSaveAsCurrentVersion, swSaveAsOptions_Silent, Nothing, errs, warns) Then
                nImg = nImg + 1
            ElseIf nImg = 0 And k = r0 Then
                gLog = gLog & "cannot save the picture " & fpath & " (errors=" & errs & ") - only playing" & vbCrLf
                imgExt = "none"
            End If
        End If
    Next k
    gSummary = "animation " & aName & ": " & nC & " component(s), frames " & r0 & ".." & r1 & " of " & nF & _
               " (" & Format(Timer - t0, "0") & " s)" & vbCrLf & _
               IIf(nImg > 0, "pictures: " & nImg & " in " & outDir, "pictures: not saved") & vbCrLf & gSummary
    BuildRobotAnim = True
End Function

' Component placed by a frame: origin (fr 0..2, mm), local X along fr 3..5, local Z along fr 6..8
Private Sub PlaceFrame(ByVal c As SldWorks.Component2, fr() As Double, ByVal k As Long)
    Dim ex(0 To 2) As Double, ez(0 To 2) As Double, ey(0 To 2) As Double, n As Double, i As Long
    Dim dd(0 To 15) As Double, mu As SldWorks.MathUtility, xf As Object, co As Object
    For i = 0 To 2
        ex(i) = fr(k, 3 + i): ez(i) = fr(k, 6 + i)
    Next i
    n = Sqr(ex(0) ^ 2 + ex(1) ^ 2 + ex(2) ^ 2): For i = 0 To 2: ex(i) = ex(i) / n: Next i
    n = Sqr(ez(0) ^ 2 + ez(1) ^ 2 + ez(2) ^ 2): For i = 0 To 2: ez(i) = ez(i) / n: Next i
    ey(0) = ez(1) * ex(2) - ez(2) * ex(1)            ' Y = Z x X
    ey(1) = ez(2) * ex(0) - ez(0) * ex(2)
    ey(2) = ez(0) * ex(1) - ez(1) * ex(0)
    For i = 0 To 2
        dd(i) = ex(i): dd(3 + i) = ey(i): dd(6 + i) = ez(i)
        dd(9 + i) = fr(k, i) * MM
    Next i
    dd(12) = 1
    Set mu = swApp.GetMathUtility
    Set xf = mu.CreateTransform(dd)
    Set co = c
    On Error Resume Next
    If Not co.SetTransformAndSolve2(xf) Then gLog = gLog & c.Name2 & ": cannot place the component" & vbCrLf
    If Err.Number <> 0 Then gLog = gLog & c.Name2 & ": cannot place the component (" & Err.Description & ")" & vbCrLf
    On Error GoTo 0
End Sub

' Component of a part anywhere below a component (name contains partName)
Private Function FindDeep(ByVal parent As SldWorks.Component2, ByVal partName As String) As SldWorks.Component2
    Dim ch As Variant, c As Variant, r As SldWorks.Component2
    ch = parent.GetChildren
    If IsEmpty(ch) Then Exit Function
    For Each c In ch
        If InStr(1, c.Name2, partName, vbTextCompare) > 0 Then
            Set FindDeep = c
            Exit Function
        End If
    Next c
    For Each c In ch
        Set r = FindDeep(c, partName)
        If Not r Is Nothing Then Set FindDeep = r: Exit Function
    Next c
End Function

' First argument of the first line starting with a keyword ("" if none)
Private Function FirstArg(ByVal path As String, ByVal kw As String) As String
    Dim lines() As String, li As Long, s As String, t() As String
    lines = ReadLines(path)
    For li = LBound(lines) To UBound(lines)
        s = CleanLine(lines(li))
        If s <> "" Then
            t = Split(s, " ")
            If UCase(t(0)) = kw And UBound(t) >= 1 Then FirstArg = t(1): Exit Function
        End If
    Next li
End Function

Private Function InsertFloating(ByVal am As SldWorks.ModelDoc2, ByVal asm As SldWorks.AssemblyDoc, _
                                ByVal path As String) As SldWorks.Component2
    Dim c As SldWorks.Component2
    LoadHidden path
    Set c = asm.AddComponent5(path, swAddComponentConfigOptions_CurrentSelectedConfig, "", False, "", 0, 0, 0)
    If c Is Nothing Then
        gLog = gLog & "Cannot insert " & path & vbCrLf
        Exit Function
    End If
    am.ClearSelection2 True
    c.Select4 False, Nothing, False
    asm.UnfixComponent
    am.ClearSelection2 True
    Set InsertFloating = c
End Function

' Front/Top/Right of the component <-> Front/Top/Right of the assembly
Private Sub MateToPlanes(ByVal am As SldWorks.ModelDoc2, ByVal asm As SldWorks.AssemblyDoc, _
                         ByVal c As SldWorks.Component2, asmPlanes() As SldWorks.Feature)
    Dim k As Long
    For k = 0 To 2
        MatePair am, asm, asmPlanes(k), FirstPlanes(c, k), swMateCOINCIDENT, c.Name2 & ": mate " & (k + 1)
    Next k
End Sub

Private Function FirstPlanes(ByVal c As SldWorks.Component2, ByVal k As Long) As SldWorks.Feature
    Dim cp(0 To 2) As SldWorks.Feature
    If GetRefPlanes(c.FirstFeature, cp) Then Set FirstPlanes = cp(k)
End Function

' Component turned by 180 deg about Y if flip and moved to x (mm); identity if not placed
Private Sub PlaceComp(ByVal c As SldWorks.Component2, ByVal x As Double, ByVal flip As Boolean, _
                      ByVal placed As Boolean)
    Dim d(0 To 15) As Double, mu As SldWorks.MathUtility, xf As Object, co As Object
    If Not placed Then x = 0: flip = False
    d(0) = IIf(flip, -1, 1): d(4) = 1: d(8) = IIf(flip, -1, 1)
    d(9) = x * MM
    d(12) = 1
    Set mu = swApp.GetMathUtility
    Set xf = mu.CreateTransform(d)
    Set co = c
    On Error Resume Next
    If Not co.SetTransformAndSolve2(xf) Then gLog = gLog & c.Name2 & ": cannot place the component" & vbCrLf
    If Err.Number <> 0 Then gLog = gLog & c.Name2 & ": cannot place the component (" & Err.Description & ")" & vbCrLf
    On Error GoTo 0
End Sub

Private Sub FixComp(ByVal am As SldWorks.ModelDoc2, ByVal asm As SldWorks.AssemblyDoc, ByVal c As SldWorks.Component2)
    am.ClearSelection2 True
    c.Select4 False, Nothing, False
    asm.FixComponent
    am.ClearSelection2 True
End Sub

' Lock mate (keeps the present relative position) between two components
Private Function MateLock(ByVal am As SldWorks.ModelDoc2, ByVal asm As SldWorks.AssemblyDoc, _
                          ByVal a As SldWorks.Component2, ByVal b As SldWorks.Component2) As Object
    Dim sd As SldWorks.SelectData, errStat As Long
    am.ClearSelection2 True
    Set sd = am.SelectionManager.CreateSelectData
    sd.Mark = 1
    a.Select4 False, sd, False
    b.Select4 True, sd, False
    On Error Resume Next
    Set MateLock = asm.AddMate3(swMateLOCK, swMateAlignALIGNED, False, 0, 0, 0, 0, 0, 0, 0, 0, False, errStat)
    On Error GoTo 0
    am.ClearSelection2 True
End Function

' Child component of a sub-assembly whose name contains partName
Private Function FindChild(ByVal parent As SldWorks.Component2, ByVal partName As String) As SldWorks.Component2
    Dim ch As Variant, c As Variant
    ch = parent.GetChildren
    If IsEmpty(ch) Then Exit Function
    For Each c In ch
        If InStr(1, c.Name2, partName, vbTextCompare) > 0 Then
            Set FindChild = c
            Exit Function
        End If
    Next c
End Function

' Component card with STEP: import, turn the card axis onto +X with the card origin at 0,
' add AXIS and the PORT planes, save as <COMPONENT>.SLDPRT next to the card. With BODY lines:
' one part per body, <COMPONENT>-<body>.SLDPRT, with the PORTs named like the body.
' Returns the part path(s), several joined by "|"; "" on failure.
Private Function ImportCard(ByVal cardPath As String) As String
    Dim lines() As String, li As Long, s As String, t() As String, folder As String, q As Long
    Dim cName As String, stepFile As String, axis As String, ox As Double, oy As Double, oz As Double
    Dim pName(0 To 15) As String, pX(0 To 15) As Double, pInfo(0 To 15) As String, nP As Long, o() As String
    Dim bName(0 To 7) As String, bFile(0 To 7) As String, nB As Long, k As Long, path As String, res As String
    folder = Left(cardPath, InStrRev(cardPath, "\"))
    axis = "+X"
    lines = ReadLines(cardPath)
    For li = LBound(lines) To UBound(lines)
        s = CleanLine(lines(li))
        If s <> "" Then
            t = Split(s, " ")
            Select Case UCase(t(0))
            Case "COMPONENT": cName = t(1)
            Case "STEP": stepFile = t(1)
            Case "BODY"
                If UBound(t) >= 2 And nB <= 7 Then bName(nB) = t(1): bFile(nB) = t(2): nB = nB + 1
            Case "FRAME"
                For q = 1 To UBound(t)
                    If LCase(Left(t(q), 5)) = "axis=" Then axis = UCase(Mid(t(q), 6))
                    If LCase(Left(t(q), 7)) = "origin=" Then
                        o = Split(Mid(t(q), 8), ",")
                        If UBound(o) >= 2 Then ox = Num(o(0)): oy = Num(o(1)): oz = Num(o(2))
                    End If
                Next q
            Case "PORT"
                If UBound(t) >= 3 And nP <= 15 Then
                    If IsNumeric(Replace(t(2), ".", Mid(CStr(0.5), 2, 1))) Then
                        pName(nP) = t(1): pX(nP) = Num(t(2))
                        pInfo(nP) = "x=" & t(2) & " dir=" & t(3)
                        For q = 4 To UBound(t)
                            pInfo(nP) = pInfo(nP) & " " & t(q)
                        Next q
                        nP = nP + 1
                    End If
                End If
            End Select
        End If
    Next li
    If cName = "" Or (stepFile = "" And nB = 0) Then
        gLog = gLog & cardPath & ": COMPONENT and STEP (or BODY) lines are needed" & vbCrLf
        Exit Function
    End If

    If nB = 0 Then
        ImportCard = ImportStepPart(folder & stepFile, axis, ox, oy, oz, cName, pName, pX, pInfo, nP, "", _
                                    folder & cName & ".SLDPRT")
        Exit Function
    End If
    For k = 0 To nB - 1
        path = ImportStepPart(folder & bFile(k), "+X", 0, 0, 0, cName & "-" & bName(k), pName, pX, pInfo, nP, _
                              bName(k), folder & cName & "-" & bName(k) & ".SLDPRT")
        If path = "" Then Exit Function
        res = res & IIf(res = "", "", "|") & path
    Next k
    ImportCard = res
End Function

' One STEP file -> part: import (with a working part template), turn onto +X if needed, AXIS,
' PORT planes (only the ports named onlyPort when it is given), properties, save as outPath.
Private Function ImportStepPart(ByVal stepPath As String, ByVal axis As String, ByVal ox As Double, _
                                ByVal oy As Double, ByVal oz As Double, ByVal pname As String, _
                                portName() As String, portX() As Double, portInfo() As String, _
                                ByVal nP As Long, ByVal onlyPort As String, ByVal outPath As String) As String
    If Not FileExists(stepPath) Then
        gLog = gLog & "STEP not found: " & stepPath & vbCrLf
        Exit Function
    End If
    ' v28: a part imported before is reused (it may be open in SOLIDWORKS - then it cannot be saved
    ' again); delete the .SLDPRT or replace the STEP by a newer one to import it again
    If FileExists(outPath) Then
        Dim reuse As Boolean
        On Error Resume Next
        reuse = (FileDateTime(outPath) >= FileDateTime(stepPath))
        If Not (swApp.GetOpenDocumentByName(outPath) Is Nothing) Then reuse = True
        On Error GoTo 0
        If reuse Then
            gSummary = gSummary & Mid(outPath, InStrRev(outPath, "\") + 1) & ": imported before, reused" & vbCrLf
            ImportStepPart = outPath
            Exit Function
        End If
    End If
    Dim m As SldWorks.ModelDoc2, impData As Object, errs As Long, oldTpl As String
    If gTplPart = "" Then gTplPart = FindTemplate("prtdot", swDefaultTemplatePart, "part")
    oldTpl = swApp.GetUserPreferenceStringValue(swDefaultTemplatePart)
    If gTplPart <> "" Then swApp.SetUserPreferenceStringValue swDefaultTemplatePart, gTplPart
    On Error Resume Next
    Set impData = swApp.GetImportFileData(stepPath)
    On Error GoTo 0
    Set m = swApp.LoadFile4(stepPath, "r", impData, errs)
    swApp.SetUserPreferenceStringValue swDefaultTemplatePart, oldTpl
    If m Is Nothing Then
        gLog = gLog & "STEP import failed (" & stepPath & ", error " & errs & ")" & vbCrLf
        Exit Function
    End If
    If m.GetType <> swDocPART Then
        gLog = gLog & stepPath & " opens as an assembly - split it into BODY files (tools/step_split.py)" & vbCrLf
        Exit Function
    End If

    If Not NormalizeFrame(m, axis, ox, oy, oz, pname) Then Exit Function

    Dim planes(0 To 2) As SldWorks.Feature, f As SldWorks.Feature, k As Long
    If Not GetRefPlanes(m.FirstFeature, planes) Then
        gLog = gLog & pname & ": reference planes not found" & vbCrLf
        Exit Function
    End If
    AddAxis m, planes, pname
    For k = 0 To nP - 1
        If onlyPort = "" Or StrComp(portName(k), onlyPort, vbTextCompare) = 0 Then
            Set f = NewPlaneAtX(m, planes(2), portX(k))
            If f Is Nothing Then
                gLog = gLog & pname & ": plane PORT_" & portName(k) & " was not created" & vbCrLf
            Else
                f.Name = "PORT_" & portName(k)
            End If
            SetProp m, "PORT_" & portName(k), portInfo(k)
        End If
    Next k
    SetProp m, "STEP", Mid(stepPath, InStrRev(stepPath, "\") + 1)
    SetProp m, "FRAME", "axis=" & axis & " origin=" & ox & "," & oy & "," & oz
    m.ClearSelection2 True
    m.EditRebuild3
    m.ShowNamedView2 "*Isometric", swIsometricView
    m.ViewZoomtofit2
    ApplyColor m, pname, ""
    If SaveDoc(m, outPath) Then ImportStepPart = outPath
    CloseSaved m, False
End Function

' Move the bodies so that the card origin is at 0 and the card axis is +X. The axial span is
' compared before / after the turn: if the turn went the other way, 180 deg about Y is added.
Private Function NormalizeFrame(ByVal m As SldWorks.ModelDoc2, ByVal axis As String, ByVal ox As Double, _
                                ByVal oy As Double, ByVal oz As Double, ByVal cName As String) As Boolean
    Dim fm As Object, f As Object, bx As Variant, a0 As Double, a1 As Double   ' late-bound: argument lists differ between versions
    Dim rx As Double, ry As Double, rz As Double, ax As Integer, sg As Integer
    Set fm = m.FeatureManager
    If ox <> 0 Or oy <> 0 Or oz <> 0 Then
        SelectBodies m
        Set f = fm.InsertMoveCopyBody2(-ox * MM, -oy * MM, -oz * MM, 0, 0, 0, 0, 0, 0, 0, False, 1)
        If f Is Nothing Then gLog = gLog & cName & ": move to the card origin failed" & vbCrLf: Exit Function
    End If
    sg = IIf(Left(axis, 1) = "-", -1, 1)
    Select Case Right(axis, 1)
        Case "X": ax = 0: If sg < 0 Then ry = PI
        Case "Y": ax = 1: rz = -sg * PI / 2
        Case "Z": ax = 2: ry = sg * PI / 2
        Case Else
            gLog = gLog & cName & ": bad FRAME axis '" & axis & "'" & vbCrLf
            Exit Function
    End Select
    If rx = 0 And ry = 0 And rz = 0 Then NormalizeFrame = True: Exit Function

    m.EditRebuild3
    bx = PartBox(m)
    If sg > 0 Then a0 = bx(ax): a1 = bx(ax + 3) Else a0 = -bx(ax + 3): a1 = -bx(ax)
    SelectBodies m
    Set f = fm.InsertMoveCopyBody2(0, 0, 0, 0, 0, 0, 0, rx, ry, rz, False, 1)
    If f Is Nothing Then gLog = gLog & cName & ": turn onto the X axis failed" & vbCrLf: Exit Function
    m.EditRebuild3
    bx = PartBox(m)
    If Abs(bx(0) - a0) > 0.0001 Or Abs(bx(3) - a1) > 0.0001 Then
        SelectBodies m
        Set f = fm.InsertMoveCopyBody2(0, 0, 0, 0, 0, 0, 0, 0, PI, 0, False, 1)
        m.EditRebuild3
        bx = PartBox(m)
        If Abs(bx(0) - a0) > 0.0001 Or Abs(bx(3) - a1) > 0.0001 Then
            gLog = gLog & cName & ": the axis could not be turned onto +X - check FRAME" & vbCrLf
            Exit Function
        End If
    End If
    NormalizeFrame = True
End Function

Private Function PartBox(ByVal m As SldWorks.ModelDoc2) As Variant
    Dim pd As SldWorks.PartDoc
    Set pd = m
    PartBox = pd.GetPartBox(True)
End Function

Private Sub SelectBodies(ByVal m As SldWorks.ModelDoc2)
    Dim pd As SldWorks.PartDoc, bodies As Variant, b As Variant, sd As SldWorks.SelectData
    Set pd = m
    m.ClearSelection2 True
    bodies = pd.GetBodies2(swSolidBody, True)
    If IsEmpty(bodies) Then Exit Sub
    Set sd = m.SelectionManager.CreateSelectData
    sd.Mark = 1
    For Each b In bodies
        b.Select2 True, sd
    Next b
End Sub

' Path from a USE / PARTS line: relative to the file's folder or to one of its parents
Private Function ResolvePath(ByVal folder As String, ByVal rel As String) As String
    Dim k As Long, f As String
    rel = Replace(rel, "/", "\")
    If Mid(rel, 2, 1) = ":" Then
        If FileExists(rel) Then ResolvePath = rel
        Exit Function
    End If
    f = folder
    For k = 0 To 5
        If FileExists(f & rel) Then ResolvePath = f & rel: Exit Function
        If Len(f) < 4 Then Exit Function
        f = Left(f, InStrRev(Left(f, Len(f) - 1), "\"))
    Next k
End Function

Private Function FileHasKeyword(ByVal path As String, ByVal kw As String) As Boolean
    Dim lines() As String, li As Long, s As String
    lines = ReadLines(path)
    For li = LBound(lines) To UBound(lines)
        s = CleanLine(lines(li))
        If UCase(Split(s & " ", " ")(0)) = kw Then FileHasKeyword = True: Exit Function
    Next li
End Function

' Save a new document. The return value of Extension.SaveAs is not reliable,
' so success is checked by the file on disk; SaveAs3 is the fallback.
Private Function SaveDoc(ByVal m As SldWorks.ModelDoc2, ByVal outPath As String) As Boolean
    Dim errs As Long, warns As Long, ok As Boolean, code3 As Long

    If FileExists(outPath) Then
        On Error Resume Next
        SetAttr outPath, vbNormal       ' clear read-only flag of an old copy
        On Error GoTo 0
    End If

    ok = m.Extension.SaveAs(outPath, swSaveAsCurrentVersion, swSaveAsOptions_Silent, _
                            Nothing, errs, warns)
    If ok Or (FileExists(outPath) And m.GetPathName <> "") Then
        SaveDoc = True
        Exit Function
    End If

    code3 = m.SaveAs3(outPath, swSaveAsCurrentVersion, swSaveAsOptions_Silent)
    If code3 = 0 Or (FileExists(outPath) And m.GetPathName <> "") Then
        SaveDoc = True
        Exit Function
    End If

    gLog = gLog & "Cannot save " & outPath & vbCrLf & _
           "  SaveAs: errors=" & errs & ", warnings=" & warns & "; SaveAs3 code=" & code3 & vbCrLf & _
           "  Check that the folder is writable and no file with this name is open." & vbCrLf
End Function
