from BCO.Instruments import Radar,Windlidar
from BCO.tools.tools import time2num,num2time
from datetime import datetime as dt
from datetime import timedelta
import matplotlib.pyplot as plt
import matplotlib as mpl
import matplotlib.patches as mpatches
import numpy as np
from scipy import ndimage
from scipy.ndimage.morphology import binary_erosion
import seaborn

def getStartEnd():
    """
    Determine the start and end values for this script.

    Returns:
        start: datetime.datetime-obj
        end: datetime.datetime-obj
    """
    date = dt.today() - timedelta(days=1)
    start = dt(date.year,date.month,date.day,0,0,0)
    end = dt(date.year,date.month,date.day,23,59,59)

    return start,end

def countClouds(radarVel):
    """
    Function to label all values belonging to one cloud with the same number.

    Args:
        radarVel: np.array of the radar Velocities or Reflection

    Returns:
        np.array where each cloud now is a cluster of the same number. Each cloud gets a new number.
    """

    radarVel[np.isnan(radarVel)] = -999
    mask = radarVel >  -998
    structure_array = np.ones([3,3])
    label_im, nb_labels = ndimage.label(mask, structure=structure_array)
    print("Clouds in picture: %i" %nb_labels)
    label_im = label_im.astype(float)
    label_im[label_im == -999] = np.nan
    return label_im, nb_labels

def cloudShapes(im):
    """
    Function to get the Contours of clouds from Radar Data.

    Args:
        im: Array where clouds have only one value (return of countClouds)

    Returns:
        np.array where the contours of clouds are marked as 1, the rest is set to np.nan. The value [0,0] of the array
        is set to -9999 for the right coloring later.
    """
    im[np.where(im != 0)] = 1

    im1 = binary_erosion(im,iterations=2)

    im = np.subtract(im,im1)

    im[np.where(im == 0)] = np.nan

    im[0,0] = -9999

    return im

def getRainmask(vel,ref):
    mask = np.asarray(ref)
    mask[np.less(mask,999999)] = np.nan #setting whole mask to nan
    mask[np.less(vel,-1.5)] = 1
    mask[0,0] = -9999
    return mask

def noDataMask(lidarVel):
    mask = np.asarray(lidarVel.copy())
    mask[np.less(mask,999999)] = np.nan #setting whole mask to nan
    mask[np.isnan(lidarVel)] = 1
    mask[0,0] = -9999
    return mask

def plotData(lidarTime,lidarRange,lidarVel,coralTime,coralRange,coralVel,coralRef,threshold):
    """
    Function for actually creating the plot.

    """
    font_size = 16
    colors = "bwr"

    fig,(ax1,ax2,ax3,ax4) = plt.subplots(nrows=4,ncols=1,figsize=(16,9),sharex=False,sharey=True)
    fig.suptitle("Vertical Velocities from Radar and Lidar", fontsize=20)

    rain_patch = mpatches.Patch(color='lime', label='Precipitation')
    noData_patch = mpatches.Patch(color='dimgrey', label='Out of Lidar Range')

    label_im,nb_labels = countClouds(coralVel.copy())
    label_im = cloudShapes(label_im)
    rainmask = getRainmask(coralVel,coralRef)
    noData = noDataMask(lidarVel)

    axes = [ax1,ax2,ax3,ax4]
    timesteps = [int((len(coralTime)/4)*i) for i in range(5)]
    timesteps[-1] -= 1
    timetups = [(timesteps[i],timesteps[i+1]) for i in range(4)]

    ax1.legend(handles=[rain_patch, noData_patch], bbox_to_anchor=(1.01, 1), loc=2, borderaxespad=0.,fontsize=font_size)
    for ax,step in zip(axes,timetups):
        print(step)
        ax.set_ylim(0,2000)
        ax.set_xlim(coralTime[step[0]],coralTime[step[1]])
        ax.contourf(lidarTime, lidarRange, lidarVel.transpose(), cmap=colors) # Lidar Data
        ax.contourf(lidarTime,lidarRange,noData.transpose(),cmap="Accent") # Above Lidar Range
        im = ax.contourf(coralTime, coralRange, coralVel.transpose(), cmap=colors) # Rada Data
        ax.contourf(coralTime,coralRange,rainmask.transpose(),cmap="brg") # Mask for Rain
        ax.contourf(coralTime, coralRange, label_im.transpose(), cmap="binary") # Mask for cloud contours
        ax.tick_params(labelsize=font_size)

        ax.set_ylabel("Height [m]",fontsize=font_size)



    ax.set_xlabel("Time [UTC]",fontsize=font_size) # set xlabel just on the last plot

    plt.tight_layout()

    fig.subplots_adjust(right=0.8,top=0.92)
    cbar_ax = fig.add_axes([0.85,0.15,0.02,0.6])

    norm = mpl.colors.Normalize(vmin=-threshold,vmax=threshold)
    cb = mpl.colorbar.ColorbarBase(cbar_ax,cmap=colors,norm=norm,orientation="vertical",extend="both")
    cb.ax.tick_params(labelsize=font_size)
    cb.set_label("Vertical Velocity [ms$^{-1}$]",fontsize=font_size)

    plt.savefig("Velocities.png")

def roundLidarVel(lidarTime,lidarVel,lidarInt):
    """
    Function to lower the amount of data used. The lidar has a temporal resolution of about 1s. Plotting all this data
    takes ages and does not bring any more information in this case than a 10s resolution data. Therefore this function
    smallers the original temporal resolution by a factor 7.

    Args:
        lidarTime: np.array of the timesteps of the lidar
        lidarVel: np.array of the Velocities of the lidar
        lidarInt: np.array of the Intensities of the backscatterering function of the Lidar

    Returns:
        All inputs reduced in size by a factor 7.

    """
    lidarTimeNew = np.asarray(lidarTime[::7])
    lidarVelNew = np.asarray(lidarVel[::7,:])
    lidarIntNew = np.asarray(lidarInt[::7,:])
    return lidarTimeNew,lidarVelNew,lidarIntNew


def filterWindLidar(lidarVel,lidarInt,windFilter=-18.3):
    """
    Function to filter out the noise of the Windlidar (copied from Aude Untersee (MPI))

    Args:
        lidarVel: np.array of the Velocities of the lidar
        lidarInt: np.array of the Intensities of the backscatterering function of the Lidar
        windFilter: The Filter-value in dBZ

    Returns:
        lidarVelFiltered: np.array of the filtered Velocities

    """
    SNR = np.subtract(lidarInt,1)
    SNR_dB = np.multiply(10,np.log10(SNR)) #SNR in dBz
    lidarVelFiltered = np.where(np.less_equal(SNR_dB,windFilter),np.nan,lidarVel)
    return lidarVelFiltered


if __name__ == "__main__":
    # seaborn.set()

    # ================================
    # Load Data:
    # ================================

    start,end = getStartEnd()
    coral = Radar(start,end,version=2)
    lidar = Windlidar(start,end)

    coralTime = coral.getTime()
    lidarTime = lidar.getTime()

    coralRange = coral.getRange()
    lidarRange = lidar.getRange()

    coralVel = coral.getVelocity()
    lidarVel = lidar.getVelocity()

    lidarInt = lidar.getIntensity()
    coralRef = coral.getReflectivity()



    # ================================
    # Adjusting Data for Plotting:
    # ================================

    lidarTime,lidarVel,lidarInt = roundLidarVel(lidarTime,lidarVel,lidarInt) # make the timeresolution ca. 10s
    lidarVel = filterWindLidar(lidarVel,lidarInt)

    coralRef[np.less(coralRef, -50)] = np.nan  # Filter all values smaller than -50 dbZ
    coralVel[np.isnan(coralRef)] = np.nan # Applying the same filter to the Velocities

    lidarVel[:, 33:][np.greater_equal(abs(lidarVel[:, 33:]), 3)] = np.nan  # removes noise above 1km

    #Setting everything above the threshold to threshold, to make smaller values visible

    threshold = 2
    lidarVel[np.greater(lidarVel,threshold)] = threshold
    coralVel[np.greater(coralVel,threshold)] = threshold
    lidarVel[np.less(lidarVel,-threshold)] = -threshold
    coralVel[np.less(coralVel,-threshold)] = -threshold

    # lidarVel[np.less(abs(lidarVel),0.2)] = 0 # set all values around 0 to 0 for harsher contours



    # =================================
    # Plotting:
    # =================================

    plotData(lidarTime,lidarRange,lidarVel,coralTime,coralRange,coralVel,coralRef,threshold)