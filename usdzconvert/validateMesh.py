import argparse
import os, shutil, sys

from pxr import *

class TermColors:
	WARN = '\033[93m'
	FAIL = '\033[91m'
	END = '\033[0m'

def _Print(stream, msg):
	print >>stream, msg

def _Err(msg):
	sys.stderr.write(TermColors.FAIL + msg + TermColors.END + '\n')

def _Warn(msg):
	sys.stderr.write(TermColors.WARN + msg + TermColors.END + '\n')

def validateTopology(faceVertexCounts, faceVertexIndices, pointsCount, meshPath, verboseOutput):
	if len(faceVertexIndices) < len(faceVertexCounts):
		if verboseOutput: _Warn("\t" + meshPath + ": faceVertexIndices's size is less then the size of faceVertexCounts.")
		return False
	return True

def validateGeomsubset(subset, facesCount, subsetName, timeCode, verboseOutput):
	indicesAttr = subset.GetIndicesAttr()
	indices = []
	if indicesAttr:
		indices = indicesAttr.Get(timeCode)

	if len(indices) == 0 or len(indices) > facesCount:
		if verboseOutput: _Warn("\tsubset " + subsetName + "'s faceIndices are invalid.")
		return False
	return True

def validateMeshAttribute(meshPath, value, indices, attrName, typeName, interpolation, elementSize, facesCount,
						  faceVertexIndicesCount, pointsCount, verboseOutput, unauthoredValueIndex = None):
	valueCount = len(value)
	if not typeName.isArray:
		valueCount = 1
	indicesCount = len(indices)

	if interpolation == UsdGeom.Tokens.constant:
		if not valueCount == elementSize:
			if verboseOutput: _Warn("\t" + meshPath + ": " + attrName + " has constant interpolation and number of value "
									+ str(valueCount) + " is not equal to element size " + str(elementSize) + ".")
			return False
	elif interpolation == UsdGeom.Tokens.vertex or interpolation == UsdGeom.Tokens.varying:
		if indicesCount > 0:
			if indicesCount != pointsCount:
				if verboseOutput: _Warn("\t" + meshPath + ": " + attrName + " has " + interpolation +
										" interpolation and number of attribute indices " + str(indicesCount) +
										" is not equal to points count " + str(pointsCount) + ".")
				return False
		else:
			if valueCount != pointsCount * elementSize:
				if verboseOutput: _Warn("\t" + meshPath + ": " + attrName + " has "+ interpolation +
										" interpolation and no indices. The number of value " + str(valueCount) +
										" is not equal to points count (" + str(pointsCount) + ") * elementSize (" +
										str(elementSize) + ").")
				return False
	elif interpolation == UsdGeom.Tokens.uniform:
		if indicesCount > 0:
			if indicesCount != facesCount:
				if verboseOutput: _Warn("\t" + meshPath + ": " + attrName + " has uniform interpolation and \
										number of attribute indices " + str(indicesCount) +
										" is not equal to faces count " + str(facesCount) + ".")
				return False
		else:
			if valueCount != facesCount * elementSize:
				if verboseOutput: _Warn("\t" + meshPath + ": " + attrName + " has uniform interpolation and no indices. \
										The number of value " + str(valueCount) + " is not equal to faces count (" +
										str(facesCount) + ") * elementSize (" + str(elementSize) + ").")
				return False
	elif interpolation == UsdGeom.Tokens.faceVarying:
		if indicesCount > 0:
			if indicesCount != faceVertexIndicesCount:
				if verboseOutput: _Warn("\t" + meshPath + ": " + attrName + " has face varying interpolation and number \
										of attribute indices " + str(indicesCount) + " is not equal to face vertices \
										count " + str(faceVertexIndicesCount) + ".")
				return False
		else:
			if valueCount != faceVertexIndicesCount * elementSize:
				if verboseOutput: _Warn("\t" + meshPath + ": " + attrName + " has face varying interpolation and no \
										indices. The number of value " + str(valueCount) + " is not equal to face \
										vertices count (" + str(faceVertexIndicesCount) + ") * elementSize (" +
										str(elementSize) + ").")
				return False
	else:
		if verboseOutput: _Warn("\t"+meshPath + ": " + attrName + " has unknown interpolation " + interpolation + ".")
		return False
	return True

def validatePrimvar(meshPath, primvar, facesCount, faceVertexIndicesCount, pointsCount, timeCode, verboseOutput):
	if primvar.HasAuthoredValue():
		indices = []
		if primvar.IsIndexed():
			indices = primvar.GetIndices(timeCode)
		attrName, typeName, interpolation, elementSize = primvar.GetDeclarationInfo()
		unauthoredValueIndex = primvar.GetUnauthoredValuesIndex()
		if not validateMeshAttribute(meshPath, primvar.Get(timeCode), indices, attrName, typeName, interpolation, elementSize,
									 facesCount, faceVertexIndicesCount, pointsCount, verboseOutput, unauthoredValueIndex):
			return False
	return True

def validateMesh(prim, verbose):
	verboseOutput = verbose
	meshPath = prim.GetPath().pathString
	mesh = UsdGeom.Mesh(prim)
	startTimeCode = prim.GetStage().GetStartTimeCode()

	faceVertexCounts = mesh.GetFaceVertexCountsAttr().Get(startTimeCode)
	if faceVertexCounts is None or len(faceVertexCounts) == 0:
		if verboseOutput: _Warn("\t" + meshPath + " has no face vertex counts data.")
		return True

	faceVertexIndices = mesh.GetFaceVertexIndicesAttr().Get(startTimeCode)
	if faceVertexIndices is None or len(faceVertexIndices) == 0:
		if verboseOutput: _Warn("\t" + meshPath + " has no face vertex indices data.")
		return True

	points = mesh.GetPointsAttr().Get(startTimeCode)
	if points is None or len(points) == 0:
		if verboseOutput: _Warn("\t" + meshPath + " has no position data.")
		return True

	pointsCount = len(points)
	if not validateTopology(faceVertexCounts, faceVertexIndices, pointsCount, meshPath, verboseOutput):
		if verboseOutput: _Err("\t " + meshPath + " has invalid topology")
		return False

	facesCount = len(faceVertexCounts)
	faceVertexIndicesCount = len(faceVertexIndices)

	subsets = UsdGeom.Subset.GetGeomSubsets(mesh)
	for subset in subsets:
		if not validateGeomsubset(subset, facesCount, subset.GetPrim().GetName(), startTimeCode, verboseOutput):
			return False
	# handle normal attribute that's not authored as primvar
	normalAttr = mesh.GetNormalsAttr()
	if normalAttr.HasAuthoredValue():
		if not validateMeshAttribute(meshPath, normalAttr.Get(startTimeCode), [], normalAttr.GetName(),
									 Sdf.ValueTypeNames.Normal3fArray, mesh.GetNormalsInterpolation(), 1, facesCount,
									 faceVertexIndicesCount, pointsCount, verboseOutput, None):
			return False

	prim = UsdGeom.PrimvarsAPI(mesh)
	# Find inherited primvars includes the primvars on prim
	inheritedPrimvars = prim.FindPrimvarsWithInheritance()
	for primvar in inheritedPrimvars:
		if not validatePrimvar(meshPath, primvar, facesCount, faceVertexIndicesCount, pointsCount, startTimeCode, verboseOutput):
			return False

	return True
