Attribute VB_Name = "BuildFromSpec"
' ============================================================================
' BuildFromSpec - SolidWorks 2017 VBA macro
'
' Reads a text spec (see README.md, examples/*.txt) and builds:
'   * every PART as a separate .SLDPRT with a feature tree:
'       Front Plane -> "Profile" sketch -> "Body" (Revolve 360)
'       -> "HolesN" (Cut-Extrude on an offset plane, circular hole pattern)
'   * if ASSEMBLY is given - an .SLDASM with all parts, each mated to the
'     assembly origin planes (3 coincident mates).
' Files are saved into the folder of the spec file.
'
' Coordinates: X - along the axis of rotation, Y - radius, mm.
' ============================================================================
Option Explicit

Private Const MM As Double = 0.001          ' SolidWorks API works in meters
Private Const PI As Double = 3.14159265358979

Private Type HoleSpec
    X As Double         ' face position along the axis, mm
    Dir As Integer      ' +1 - drill towards +X, -1 - towards -X
    N As Long           ' number of holes
    Pcd As Double       ' pitch circle diameter, mm
    D As Double         ' hole diameter, mm
    Depth As Double     ' depth, mm (0 = through all)
    Ang As Double       ' angle of the first hole, deg
End Type

Private Type PartSpec
    Name As String
    PX() As Double
    PY() As Double
    NP As Long
    H() As HoleSpec
    NH As Long
End Type

Private swApp As SldWorks.SldWorks
Private gParts() As PartSpec
Private gNParts As Long
Private gAsmName As String
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
        MsgBox "Finished with warnings:" & vbCrLf & gLog, vbInformation
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
    Dim lineNo As Long, cur As Long, k As Long, errMsg As String

    cur = -1: gNParts = 0: gAsmName = ""
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

        Case Else
            errMsg = "unknown keyword '" & t(0) & "'": GoTo Bad
        End Select
NextLine:
    Next li

    If gNParts = 0 Then
        MsgBox "No PART found in the spec.", vbExclamation
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
        AddHoles m, planes(2), p.H(i), i + 1, p.Name
    Next i

    m.ClearSelection2 True
    m.EditRebuild3
    m.ShowNamedView2 "*Isometric", swIsometricView
    m.ViewZoomtofit2

    Dim errs As Long, warns As Long
    If Not m.Extension.SaveAs(outPath, swSaveAsCurrentVersion, swSaveAsOptions_Silent, _
                              Nothing, errs, warns) Then
        gLog = gLog & "Cannot save " & outPath & " (error " & errs & "). " & _
               "Close old copies of this file and run again." & vbCrLf
        Exit Function
    End If
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
    Set sm = m.SketchManager
    m.ClearSelection2 True
    pl.Select2 False, 0
    sm.InsertSketch True
    For i = 0 To h.N - 1
        a = (h.Ang + i * 360# / h.N) * PI / 180#
        sm.CreateCircleByRadius h.Pcd / 2 * Cos(a) * MM, h.Pcd / 2 * Sin(a) * MM, 0, h.D / 2 * MM
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

    Dim nm As String, pd As SldWorks.PartDoc, f As SldWorks.Feature, rp As SldWorks.RefPlane
    nm = "Plane_X" & Replace(CStr(x), ",", ".")
    Set pd = m
    Set f = pd.FeatureByName(nm)
    If Not f Is Nothing Then
        Set GetOffsetPlane = f
        Exit Function
    End If

    m.ClearSelection2 True
    rightPlane.Select2 False, 0
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

    f.Name = nm
    m.ClearSelection2 True
    f.Select2 False, 0
    m.BlankRefGeom          ' hide the helper plane
    m.ClearSelection2 True
    Set GetOffsetPlane = f
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

    Dim i As Long, k As Long, comp As SldWorks.Component2
    Dim mate As SldWorks.Feature, errStat As Long
    For i = LBound(partPaths) To UBound(partPaths)
        Set comp = asm.AddComponent5(partPaths(i), swAddComponentConfigOptions_CurrentSelectedConfig, _
                                     "", False, "", 0, 0, 0)
        If comp Is Nothing Then
            gLog = gLog & "Cannot insert " & partPaths(i) & vbCrLf
        Else
            ' float the component, then fix its position by mates
            am.ClearSelection2 True
            comp.Select4 False, Nothing, False
            asm.UnfixComponent
            If GetRefPlanes(comp.FirstFeature, cp) Then
                For k = 0 To 2
                    am.ClearSelection2 True
                    asmPlanes(k).Select2 False, 1
                    cp(k).Select2 True, 1
                    Set mate = asm.AddMate3(swMateCOINCIDENT, swMateAlignALIGNED, False, _
                                            0, 0, 0, 0, 0, 0, 0, 0, False, errStat)
                    If mate Is Nothing Then
                        gLog = gLog & comp.Name2 & ": mate " & (k + 1) & " failed (status " & errStat & ")" & vbCrLf
                    End If
                Next k
            Else
                gLog = gLog & comp.Name2 & ": planes not found, component left floating" & vbCrLf
            End If
        End If
    Next i

    am.ClearSelection2 True
    am.EditRebuild3
    am.ShowNamedView2 "*Isometric", swIsometricView
    am.ViewZoomtofit2

    Dim errs As Long, warns As Long
    If Not am.Extension.SaveAs(asmPath, swSaveAsCurrentVersion, swSaveAsOptions_Silent, _
                               Nothing, errs, warns) Then
        gLog = gLog & "Cannot save " & asmPath & " (error " & errs & ")" & vbCrLf
    End If
End Sub
