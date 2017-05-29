from geokit._core.regionmask import *
from os.path import basename


def combineSimilarRasters(master, datasets, combiningFunc=None, verbose=True, **kwargs):
    """!!! WRITE ME !!!"""

    # Ensure we have a list of raster datasets
    if isinstance(datasets, str):
        datasets = glob(datasets)
        datasets.sort()
    elif isinstance(datasets, gdal.Dataset):
        datasets = [datasets,]
    else: # assume datasets is iterable
        datasets = list(datasets)

    if len(datasets)==0: raise GeoKitError("No datasets given")
    
    # Determine info for all datasets
    infoSet = [rasterInfo(d) for d in datasets]

    # Ensure all input rasters share resolution, srs, datatype, and noData
    for info in infoSet[1:]:
        if not info.srs.IsSame(infoSet[0].srs):
            raise GeoKitError("SRS does not match in datasets")
        if not (info.dx == infoSet[0].dx and info.dy == infoSet[0].dy) :
            raise GeoKitError("Resolution does not match in datasets")
        if not (info.dtype == infoSet[0].dtype) :
            raise GeoKitError("Datatype does not match in datasets")
    
    # Get summary info about the whole dataset group 
    dataXMin = min([i.xMin for i in infoSet])
    dataXMax = max([i.xMax for i in infoSet])
    dataYMin = min([i.yMin for i in infoSet])
    dataYMax = max([i.yMax for i in infoSet])
    
    # Maybe create a new master dataset
    if not (os.path.isfile(master)): # we will need to create a master source
        # Determine no data value
        noDataValue = kwargs.pop("noDataValue", None)

        if noDataValue is None:
            noDataSet = set([i.noData for i in infoSet])
            if len(noDataSet)==1: noDataValue = noDataSet.pop()
            
        # Create Raster
        dx = infoSet[0].dx
        dy = infoSet[0].dy
        dtype = infoSet[0].dtype
        srs = infoSet[0].srs
        
        createRaster(bounds=(dataXMin, dataYMin, dataXMax, dataYMax), output=master, 
                     dtype=dtype, pixelWidth=dx, pixelHeight=dy, noDataValue=noDataValue, 
                     srs=srs, fillValue=noDataValue, **kwargs)

    # Open master dataset and check parameters
    masterDS = gdal.Open(master, gdal.GA_Update)
    mInfo = rasterInfo(masterDS)
    mExtent = Extent(mInfo.bounds, srs=mInfo.srs)

    if not mInfo.srs.IsSame(infoSet[0].srs):
        raise GeoKitError("SRS's do not match master dataset")
    if not (mInfo.dx == infoSet[0].dx and mInfo.dy == infoSet[0].dy) :
        raise GeoKitError("Resolution's do not match master dataset")
    if not (mInfo.dtype == infoSet[0].dtype) :
        raise GeoKitError("Datatype's do not match master dataset")
    
    masterBand = masterDS.GetRasterBand(1)

    # Add each dataset to master
    for i in range(len(datasets)):
        if verbose: 
            if isinstance(datasets[i], str): print(i, basename(datasets[i]))
            else: print(i)
        # create dataset extent
        dExtent = Extent(infoSet[i].bounds, srs=infoSet[i].srs)

        # Fetch the dataset's matrix
        dMatrix = fetchMatrix(datasets[i])
        if not infoSet[i].yAtTop:
            dMatrix = dMatrix[::-1,:]

        # Calculate starting indicies
        idx = mExtent.findWithin(dExtent, (mInfo.dx, mInfo.dy), yAtTop=mInfo.yAtTop)

        # Get master data

        mMatrix = masterBand.ReadAsArray(xoff=idx.xStart, yoff=idx.yStart, win_xsize=idx.xWin, win_ysize=idx.yWin)

        # create selector
        if not combiningFunc is None:
            writeMatrix = combiningFunc(mMatrix=mMatrix, mInfo=mInfo, dMatrix=dMatrix, dInfo=infoSet[i])
        elif (not infoSet[i].noData is None):
            sel = dMatrix!=infoSet[i].noData
            mMatrix[sel] = dMatrix[sel]
            writeMatrix = mMatrix
        else: 
            writeMatrix = dMatrix

        # Add to master
        masterBand.WriteArray(writeMatrix, idx.xStart, idx.yStart)
        masterBand.FlushCache()
    
    # Write final raster
    del masterBand
    masterDS.FlushCache()
    calculateStats(masterDS)
