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
'     PORT lines -> "PORT_<name>" plane + custom property of the part.
' Files are saved into the folder of the spec file.
'
' Coordinates: X - along the axis of rotation, Y - radius, mm.
' ============================================================================
Option Explicit

Private Const MM As Double = 0.001          ' SolidWorks API works in meters
Private Const PI As Double = 3.14159265358979
Private Const AXIS_NAME As String = "AXIS"
Private Const MACRO_VERSION As String = "v13 (2026-10-17)"

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
End Type

Private swApp As SldWorks.SldWorks
Private gParts() As PartSpec
Private gNParts As Long
Private gAsmName As String
Private gData As String          ' "key=value key=value ..." from DATA lines
Private gLog As String

Sub main()
    Set swApp = Application.SldWorks
    gLog = ""

    Dim specPath As String
    specPath = PickSpecFile()
    If specPath = "" Then Exit Sub
    If Not FileExists(specPath) Then
        MsgBox "File not found or bad path:" & vbCrLf & specPath, vbExclamation
        Exit Sub
    End If
    If Not ReadSpec(specPath) Then Exit Sub

    Dim folder As String
    folder = Left(specPath, InStrRev(specPath, "\"))

    Dim partPaths() As String, i As Long
    ReDim partPaths(0 To gNParts - 1)
    For i = 0 To gNParts - 1
        partPaths(i) = folder & gParts(i).Name & ".SLDPRT"
        If Not BuildPart(gParts(i), partPaths(i)) Then
            MsgBox "Part " & gParts(i).Name & " was not built:" & vbCrLf & gLog, vbExclamation
            Exit Sub
        End If
    Next i

    If gAsmName <> "" Then BuildAssembly folder & gAsmName & ".SLDASM", partPaths

    If gLog <> "" Then
        MsgBox "Finished with warnings (" & MACRO_VERSION & "):" & vbCrLf & gLog, vbInformation
    End If
End Sub

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
            gParts(cur).NPort = 0
            ReDim gParts(cur).PortName(0 To 7)
            ReDim gParts(cur).PortX(0 To 7)
            ReDim gParts(cur).PortInfo(0 To 7)

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

        Case "COMPONENT", "TYPE", "STEP"
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

        Case "PORT"
            ' PORT name x dir [key=value ...]; outside PART (purchased parts) - ignored
            If cur >= 0 Then
                If UBound(t) < 3 Then errMsg = "expected 'PORT name x dir [key=value ...]'": GoTo Bad
                k = gParts(cur).NPort
                If k > UBound(gParts(cur).PortName) Then
                    ReDim Preserve gParts(cur).PortName(0 To 2 * k)
                    ReDim Preserve gParts(cur).PortX(0 To 2 * k)
                    ReDim Preserve gParts(cur).PortInfo(0 To 2 * k)
                End If
                gParts(cur).PortName(k) = t(1)
                gParts(cur).PortX(k) = Num(t(2))
                info = "x=" & t(2) & " dir=" & t(3)
                For q = 4 To UBound(t)
                    info = info & " " & t(q)
                Next q
                gParts(cur).PortInfo(k) = info
                gParts(cur).NPort = k + 1
            End If
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
        If gParts(cur).NP < 3 Then
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
    Set m = swApp.NewDocument(swApp.GetUserPreferenceStringValue(swDefaultTemplatePart), 0, 0, 0)
    If m Is Nothing Then
        gLog = gLog & "Cannot create a part - check the default part template." & vbCrLf
        Exit Function
    End If

    Dim planes(0 To 2) As SldWorks.Feature    ' Front, Top, Right
    If Not GetRefPlanes(m.FirstFeature, planes) Then
        gLog = gLog & "Reference planes not found in the part template." & vbCrLf
        Exit Function
    End If

    ' --- profile sketch on the Front plane ---
    Dim sm As SldWorks.SketchManager
    Set sm = m.SketchManager
    m.ClearSelection2 True
    planes(0).Select2 False, 0
    sm.InsertSketch True

    Dim i As Long, j As Long, xMin As Double, xMax As Double
    xMin = p.PX(0): xMax = p.PX(0)
    For i = 0 To p.NP - 1
        j = (i + 1) Mod p.NP
        sm.CreateLine p.PX(i) * MM, p.PY(i) * MM, 0, p.PX(j) * MM, p.PY(j) * MM, 0
        If p.PX(i) < xMin Then xMin = p.PX(i)
        If p.PX(i) > xMax Then xMax = p.PX(i)
    Next i
    sm.CreateCenterLine xMin * MM, 0, 0, xMax * MM, 0, 0
    sm.InsertSketch True

    Dim sk As SldWorks.Feature
    Set sk = m.FeatureByPositionReverse(0)
    sk.Name = "Profile"

    ' --- revolve ---
    m.ClearSelection2 True
    sk.Select2 False, 0
    Dim body As SldWorks.Feature
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
    body.Name = "Body"

    ' --- holes ---
    For i = 0 To p.NH - 1
        If p.H(i).IsThread Then
            AddThread m, planes, p, i
        Else
            AddHoles m, planes(2), p.H(i), i + 1, p.Name
        End If
    Next i

    ' --- axis of rotation and interface planes ---
    AddAxis m, planes, p.Name
    For i = 0 To p.NPort - 1
        AddPort m, planes(2), p, i
    Next i

    m.ClearSelection2 True
    m.EditRebuild3
    m.ShowNamedView2 "*Isometric", swIsometricView
    m.ViewZoomtofit2

    If Not SaveDoc(m, outPath) Then Exit Function
    BuildPart = True
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
    For i = 0 To h.N - 1
        a = (h.Ang + i * 360# / h.N) * PI / 180#
        ' hole centre in model coordinates -> sketch coordinates
        sp = ModelToSketch(xf, h.X * MM, h.Pcd / 2 * Sin(a) * MM, h.Pcd / 2 * Cos(a) * MM)
        sm.CreateCircleByRadius sp(0), sp(1), 0, h.D / 2 * MM
    Next i
    sm.InsertSketch True

    Dim sk As SldWorks.Feature
    Set sk = m.FeatureByPositionReverse(0)
    sk.Name = "Holes" & idx & "_Sketch"

    Dim cut As SldWorks.Feature, attempt As Long, rev As Boolean
    If h.Depth <= 0 Then
        m.ClearSelection2 True
        sk.Select2 False, 0
        Set cut = CutExtrude(m, False, False, swEndCondThroughAll, 0.01)
    Else
        ' first try the given direction; if the cut misses the body, try the other one
        For attempt = 0 To 1
            rev = (h.Dir < 0) Xor (attempt = 1)
            m.ClearSelection2 True
            sk.Select2 False, 0
            Set cut = CutExtrude(m, True, rev, swEndCondBlind, h.Depth * MM)
            If Not cut Is Nothing Then Exit For
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
Private Sub BuildAssembly(ByVal asmPath As String, partPaths() As String)
    Dim am As SldWorks.ModelDoc2, asm As SldWorks.AssemblyDoc
    Set am = swApp.NewDocument(swApp.GetUserPreferenceStringValue(swDefaultTemplateAssembly), 0, 0, 0)
    If am Is Nothing Then
        gLog = gLog & "Cannot create an assembly - check the default assembly template." & vbCrLf
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

    SaveDoc am, asmPath
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
