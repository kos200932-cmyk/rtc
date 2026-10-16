Attribute VB_Name = "RevolveFromProfile"
' ============================================================================
' RevolveFromProfile - SolidWorks 2017 VBA macro
'
' Builds a revolved part with a real feature tree:
'   Front Plane -> Sketch "Profile" (closed polyline + centerline) -> Revolve
' The profile is read from a text file (format: see README.md / examples).
'
' Coordinates in the file: X - along the axis of rotation, Y - radius, mm.
' The axis of rotation is the model X axis (sketch on the Front plane).
' ============================================================================
Option Explicit

Private Const MM As Double = 0.001          ' SolidWorks API works in meters
Private Const PI As Double = 3.14159265358979

Sub main()
    Dim swApp As SldWorks.SldWorks
    Set swApp = Application.SldWorks

    ' --- 1. Choose profile file -------------------------------------------
    Dim profilePath As String
    profilePath = InputBox("Full path to the profile file (*.txt):", _
                           "RevolveFromProfile", _
                           swApp.GetCurrentMacroPathFolder & "\")
    If profilePath = "" Then Exit Sub
    If Dir(profilePath) = "" Then
        MsgBox "File not found:" & vbCrLf & profilePath, vbExclamation
        Exit Sub
    End If

    ' --- 2. Read and check the profile ------------------------------------
    Dim xs() As Double, ys() As Double, n As Long, partName As String
    If Not ReadProfile(profilePath, xs, ys, n, partName) Then Exit Sub

    ' --- 3. New part ------------------------------------------------------
    Dim template As String
    template = swApp.GetUserPreferenceStringValue(swDefaultTemplatePart)
    Dim swModel As SldWorks.ModelDoc2
    Set swModel = swApp.NewDocument(template, 0, 0, 0)
    If swModel Is Nothing Then
        MsgBox "Cannot create a part. Check the default part template " & _
               "(Options - Default Templates).", vbExclamation
        Exit Sub
    End If

    ' --- 4. Sketch on the Front plane -------------------------------------
    Dim frontPlane As SldWorks.Feature
    Set frontPlane = FirstRefPlane(swModel)
    If frontPlane Is Nothing Then
        MsgBox "Front plane not found in the template.", vbExclamation
        Exit Sub
    End If
    swModel.ClearSelection2 True
    frontPlane.Select2 False, 0

    Dim sm As SldWorks.SketchManager
    Set sm = swModel.SketchManager
    sm.InsertSketch True

    Dim i As Long, j As Long
    Dim xMin As Double, xMax As Double
    xMin = xs(0): xMax = xs(0)
    For i = 0 To n - 1
        j = (i + 1) Mod n
        sm.CreateLine xs(i) * MM, ys(i) * MM, 0, xs(j) * MM, ys(j) * MM, 0
        If xs(i) < xMin Then xMin = xs(i)
        If xs(i) > xMax Then xMax = xs(i)
    Next i
    ' Axis of rotation (the only centerline -> used by Revolve automatically)
    sm.CreateCenterLine xMin * MM, 0, 0, xMax * MM, 0, 0

    sm.InsertSketch True    ' exit sketch

    Dim sketchFeat As SldWorks.Feature
    Set sketchFeat = swModel.FeatureByPositionReverse(0)
    sketchFeat.Name = "Profile"

    ' --- 5. Revolve 360 deg -----------------------------------------------
    swModel.ClearSelection2 True
    sketchFeat.Select2 False, 0

    Dim revFeat As SldWorks.Feature
    Set revFeat = swModel.FeatureManager.FeatureRevolve2( _
        True, True, False, False, False, False, _
        swEndCondBlind, swEndCondBlind, 2 * PI, 0, _
        False, False, 0, 0, _
        swThinWallOneDirection, 0, 0, _
        True, False, True)

    If revFeat Is Nothing Then
        MsgBox "Revolve failed. Check that the profile is closed, " & _
               "does not self-intersect and lies on one side of the axis.", _
               vbExclamation
        Exit Sub
    End If
    revFeat.Name = "Body"

    swModel.ClearSelection2 True
    swModel.ShowNamedView2 "*Isometric", swIsometricView
    swModel.ViewZoomtofit2

    ' --- 6. Save next to the profile file ---------------------------------
    Dim outPath As String, errs As Long, warns As Long
    outPath = Left(profilePath, InStrRev(profilePath, "\")) & partName & ".SLDPRT"
    swModel.Extension.SaveAs outPath, swSaveAsCurrentVersion, _
                             swSaveAsOptions_Silent, Nothing, errs, warns
    If errs <> 0 Then
        MsgBox "Part built, but not saved (error " & errs & "):" & vbCrLf & outPath, vbExclamation
    End If
End Sub

' Reads the profile file. Lines:
'   # comment            (also ';')
'   NAME <part name>
'   P <x> <y>            point of the closed profile, mm (decimal '.' or ',')
Private Function ReadProfile(ByVal path As String, xs() As Double, ys() As Double, _
                             n As Long, partName As String) As Boolean
    Dim f As Integer, s As String, parts() As String, lineNo As Long
    n = 0
    partName = "Part"
    ReDim xs(0 To 63): ReDim ys(0 To 63)

    f = FreeFile
    Open path For Input As #f
    Do While Not EOF(f)
        Line Input #f, s
        lineNo = lineNo + 1
        s = Trim(Replace(s, vbTab, " "))
        Do While InStr(s, "  ") > 0
            s = Replace(s, "  ", " ")
        Loop
        If s = "" Then GoTo NextLine
        If Left(s, 1) = "#" Or Left(s, 1) = ";" Then GoTo NextLine

        parts = Split(s, " ")
        Select Case UCase(parts(0))
            Case "NAME"
                If UBound(parts) >= 1 Then partName = Trim(Mid(s, 5))
            Case "P"
                If UBound(parts) < 2 Then
                    Close #f
                    MsgBox "Line " & lineNo & ": expected 'P x y'.", vbExclamation
                    Exit Function
                End If
                If n > UBound(xs) Then
                    ReDim Preserve xs(0 To 2 * n): ReDim Preserve ys(0 To 2 * n)
                End If
                xs(n) = Val(Replace(parts(1), ",", "."))
                ys(n) = Val(Replace(parts(2), ",", "."))
                If ys(n) < 0 Then
                    Close #f
                    MsgBox "Line " & lineNo & ": radius (Y) must be >= 0.", vbExclamation
                    Exit Function
                End If
                n = n + 1
            Case Else
                ' unknown keyword - ignored (reserved for future versions)
        End Select
NextLine:
    Loop
    Close #f

    ' drop the last point if it repeats the first one
    If n > 1 Then
        If xs(n - 1) = xs(0) And ys(n - 1) = ys(0) Then n = n - 1
    End If
    If n < 3 Then
        MsgBox "The profile needs at least 3 points.", vbExclamation
        Exit Function
    End If
    ReadProfile = True
End Function

' First reference plane of the part = Front plane (XY), independent of UI language
Private Function FirstRefPlane(ByVal m As SldWorks.ModelDoc2) As SldWorks.Feature
    Dim f As SldWorks.Feature
    Set f = m.FirstFeature
    Do While Not f Is Nothing
        If f.GetTypeName2 = "RefPlane" Then
            Set FirstRefPlane = f
            Exit Function
        End If
        Set f = f.GetNextFeature
    Loop
End Function
