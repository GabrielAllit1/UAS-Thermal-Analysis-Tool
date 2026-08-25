import cv2
import numpy as np
import exifread
from skimage import measure
from ctypes import cdll, c_void_p, c_uint8, c_uint32, c_uint16, c_int, c_float, byref
import rasterio
from rasterio.windows import Window
import os
import logging
import pykml.parser
from pyproj import Transformer
from lxml import etree
import traceback
import time

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load DJI Thermal SDK with full path
try:
    lib = cdll.LoadLibrary("C:\\Users\\GAllit\\ThermalAnalysis\\libdirp.dll")
except Exception as e:
    logger.error(f"Failed to load libdirp.dll: {str(e)}")
    raise Exception(f"Failed to load libdirp.dll: {str(e)}. Ensure libdirp.dll, libv_dirp.dll, and libv_girp.dll are in C:\\Users\\GAllit\\ThermalAnalysis")

# Define DIRP_RET enum
DIRP_SUCCESS = 0
DIRP_ERROR_INVALID_ARGUMENT = -1
DIRP_ERROR_INVALID_HANDLE = -2
DIRP_ERROR_MEMORY = -3
DIRP_ERROR_INTERNAL = -4

# Define palette enum
DIRP_PSEUDO_COLOR = {
    "WHITEHOT": 0,
    "BLACKHOT": 1,
    "IRONRED": 2,
    "RAINBOW": 3,
    "MEDICAL": 4,
    "ARCTIC": 5,
    "TYRIAN": 6,
    "GLOWBOW": 7
}

# Transformer for Lat/Lon (WGS84) to State Plane (EPSG:6447, Illinois State Plane West, NAD83, US Survey Feet)
transformer_to_state_plane = Transformer.from_crs("EPSG:4326", "EPSG:6447", always_xy=True)
# Transformer for State Plane to Lat/Lon
transformer_to_wgs84 = Transformer.from_crs("EPSG:6447", "EPSG:4326", always_xy=True)

def check_dirp_ret(ret, func_name):
    """Check DIRP return code and raise exception on error."""
    if ret != DIRP_SUCCESS:
        errors = {
            DIRP_ERROR_INVALID_ARGUMENT: "Invalid argument",
            DIRP_ERROR_INVALID_HANDLE: "Invalid handle",
            DIRP_ERROR_MEMORY: "Memory error",
            DIRP_ERROR_INTERNAL: "Internal error"
        }
        logger.error(f"{func_name} failed: {errors.get(ret, f'Unknown error code {ret}')}")
        raise Exception(f"{func_name} failed: {errors.get(ret, f'Unknown error code {ret}')}")

def extract_metadata(image_path):
    """Extract EXIF metadata from R-JPEG."""
    logger.info(f"Extracting metadata from R-JPEG: {image_path}")
    with open(image_path, 'rb') as f:
        tags = exifread.process_file(f)
    metadata = {}
    for tag in tags:
        if 'Thermal' not in tag:
            metadata[tag] = str(tags[tag])
    logger.info(f"Metadata extracted: {len(metadata)} tags")
    return metadata

def extract_geotiff_metadata(geotiff_path):
    """Extract metadata from GeoTIFF."""
    logger.info(f"Extracting metadata from GeoTIFF: {geotiff_path}")
    try:
        with rasterio.open(geotiff_path) as src:
            metadata = {
                "CRS": str(src.crs) if src.crs else "N/A",
                "Width": src.width,
                "Height": src.height,
                "Bands": src.count,
                "Bounds": src.bounds,
                "Resolution": src.res,
                "Profile": src.profile,
                "Transform": src.transform,
                "Description": src.descriptions if src.descriptions else "N/A",
                "Tags": src.tags(),
                "Photometric": src.profile.get('photometric', 'N/A'),
                "Compression": src.profile.get('compress', 'N/A')
            }
        logger.info(f"GeoTIFF metadata extracted: {metadata}")
        return metadata
    except Exception as e:
        logger.error(f"Failed to extract GeoTIFF metadata: {str(e)}\n{traceback.format_exc()}")
        raise

def load_tfw(tfw_path):
    """Load TFW file to get georeferencing parameters."""
    logger.info(f"Loading TFW file: {tfw_path}")
    try:
        with open(tfw_path, 'r') as f:
            lines = f.readlines()
            if len(lines) != 6:
                logger.error(f"Invalid TFW file: {tfw_path}")
                raise ValueError(f"Invalid TFW file: {tfw_path}")
            tfw_data = [float(line.strip()) for line in lines]
            return {
                'x_scale': tfw_data[0],
                'y_skew': tfw_data[1],
                'x_skew': tfw_data[2],
                'y_scale': tfw_data[3],
                'x_origin': tfw_data[4],
                'y_origin': tfw_data[5]
            }
    except Exception as e:
        logger.error(f"Failed to load TFW file {tfw_path}: {str(e)}\n{traceback.format_exc()}")
        raise

def parse_kml(kml_path):
    """Parse KML file to extract georeferencing data, including fallback bounds from placemarks."""
    logger.info(f"Parsing KML file: {kml_path}")
    try:
        with open(kml_path, 'r') as f:
            kml_doc = etree.parse(f).getroot()
    except Exception as e:
        logger.error(f"Failed to parse KML file {kml_path}: {str(e)}\n{traceback.format_exc()}")
        raise ValueError(f"Failed to parse KML file {kml_path}: {str(e)}")
    
    # Dynamically detect the namespace from the root element
    nsmap = kml_doc.nsmap
    kml_ns = nsmap.get(None, "http://www.opengis.net/kml/2.2")  # Default to standard KML namespace if None
    logger.info(f"Detected KML namespace: {kml_ns}")
    
    kml_data = {
        'bounds': None,
        'placemarks': [],
        'metadata': {}
    }
    
    # First, try to extract bounding box from GroundOverlay (preferred method)
    ground_overlays = kml_doc.xpath("//kml:GroundOverlay", namespaces={'kml': kml_ns})
    for overlay in ground_overlays:
        lat_lon_box = overlay.xpath(".//kml:LatLonBox", namespaces={'kml': kml_ns})
        if lat_lon_box:
            box = lat_lon_box[0]
            try:
                bounds = {
                    'north': float(box.xpath(".//kml:north/text()", namespaces={'kml': kml_ns})[0]),
                    'south': float(box.xpath(".//kml:south/text()", namespaces={'kml': kml_ns})[0]),
                    'east': float(box.xpath(".//kml:east/text()", namespaces={'kml': kml_ns})[0]),
                    'west': float(box.xpath(".//kml:west/text()", namespaces={'kml': kml_ns})[0])
                }
                kml_data['bounds'] = bounds
                logger.info(f"Found LatLonBox in GroundOverlay: {bounds}")
                break
            except (IndexError, ValueError) as e:
                logger.warning(f"Invalid LatLonBox data in GroundOverlay: {str(e)}")
                continue
    
    # Extract placemarks
    placemarks = []
    for placemark in kml_doc.xpath("//kml:Placemark", namespaces={'kml': kml_ns}):
        name = placemark.xpath(".//kml:name", namespaces={'kml': kml_ns})
        name = str(name[0]) if name else "Unnamed"
        point = placemark.xpath(".//kml:Point/kml:coordinates", namespaces={'kml': kml_ns})
        if point:
            coords = str(point[0]).strip().split(',')
            if len(coords) >= 2:
                try:
                    lon, lat = float(coords[0]), float(coords[1])
                    placemarks.append({'name': name, 'latitude': lat, 'longitude': lon})
                except ValueError as e:
                    logger.warning(f"Invalid coordinates in placemark {name}: {str(e)}")
                    continue
    kml_data['placemarks'] = placemarks
    
    # If no LatLonBox was found, infer bounds from placemarks (if there are at least 2)
    if not kml_data['bounds'] and len(placemarks) >= 2:
        lats = [p['latitude'] for p in placemarks]
        lons = [p['longitude'] for p in placemarks]
        # Add a small buffer (e.g., 0.001 degrees) to ensure coverage
        buffer = 0.001
        bounds = {
            'north': max(lats) + buffer,
            'south': min(lats) - buffer,
            'east': max(lons) + buffer,
            'west': min(lons) - buffer
        }
        kml_data['bounds'] = bounds
        logger.info(f"Inferred bounds from placemarks: {bounds}")
    
    # Extract metadata (description, extended data, etc.)
    description = kml_doc.xpath("//kml:Document/kml:description", namespaces={'kml': kml_ns})
    if description:
        kml_data['metadata']['description'] = str(description[0])
    
    extended_data = kml_doc.xpath("//kml:Document/kml:ExtendedData/kml:Data", namespaces={'kml': kml_ns})
    for data in extended_data:
        name = data.get('name', 'unknown')
        value = data.xpath(".//kml:value", namespaces={'kml': kml_ns})
        value = str(value[0]) if value else "N/A"
        kml_data['metadata'][name] = value
    
    logger.info(f"KML data extracted: bounds={kml_data['bounds']}, placemarks={len(kml_data['placemarks'])}, metadata={kml_data['metadata']}")
    return kml_data

def latlon_to_pixel(lat, lon, kml_bounds, width, height):
    """Convert Lat/Lon to pixel coordinates using KML bounding box."""
    try:
        if not kml_bounds or not all([kml_bounds['north'], kml_bounds['south'], kml_bounds['east'], kml_bounds['west']]):
            raise ValueError("KML bounding box is incomplete or invalid")
        
        # Normalize coordinates to [0, 1] range within the bounding box
        lat_range = kml_bounds['north'] - kml_bounds['south']
        lon_range = kml_bounds['east'] - kml_bounds['west']
        
        if lat_range == 0 or lon_range == 0:
            raise ValueError("KML bounds have zero range (north-south or east-west)")
        
        x_norm = (lon - kml_bounds['west']) / lon_range
        y_norm = (kml_bounds['north'] - lat) / lat_range
        
        # Map to pixel coordinates
        pixel_x = x_norm * width
        pixel_y = y_norm * height
        
        # Ensure pixel coordinates are within image bounds
        pixel_x = max(0, min(width - 1, pixel_x))
        pixel_y = max(0, min(height - 1, pixel_y))
        
        logger.debug(f"Converted Lat/Lon ({lat}, {lon}) to pixel ({pixel_x}, {pixel_y})")
        return pixel_x, pixel_y
    except Exception as e:
        logger.error(f"Error in latlon_to_pixel: {str(e)}\n{traceback.format_exc()}")
        raise

def pixel_to_latlon(pixel_x, pixel_y, kml_bounds, width, height):
    """Convert pixel coordinates to Lat/Lon using KML bounding box."""
    try:
        if not kml_bounds or not all([kml_bounds['north'], kml_bounds['south'], kml_bounds['east'], kml_bounds['west']]):
            raise ValueError("KML bounding box is incomplete or invalid")
        
        if width <= 0 or height <= 0:
            raise ValueError(f"Invalid image dimensions: width={width}, height={height}")
        
        # Normalize pixel coordinates to [0, 1] range
        x_norm = pixel_x / width
        y_norm = pixel_y / height
        
        # Map to Lat/Lon
        lat_range = kml_bounds['north'] - kml_bounds['south']
        lon_range = kml_bounds['east'] - kml_bounds['west']
        
        if lat_range == 0 or lon_range == 0:
            raise ValueError("KML bounds have zero range (north-south or east-west)")
        
        lon = kml_bounds['west'] + (x_norm * lon_range)
        lat = kml_bounds['north'] - (y_norm * lat_range)
        
        logger.debug(f"Converted pixel ({pixel_x}, {pixel_y}) to Lat/Lon ({lat}, {lon})")
        return lat, lon
    except Exception as e:
        logger.error(f"Error in pixel_to_latlon: {str(e)}\n{traceback.format_exc()}")
        raise

def pixel_to_coords(pixel_x, pixel_y, tfw_data):
    """Convert pixel coordinates to State Plane coordinates using TFW data."""
    try:
        x = tfw_data['x_origin'] + (pixel_x * tfw_data['x_scale']) + (pixel_y * tfw_data['x_skew'])
        y = tfw_data['y_origin'] + (pixel_x * tfw_data['y_skew']) + (pixel_y * tfw_data['y_scale'])
        logger.debug(f"Converted pixel ({pixel_x}, {pixel_y}) to State Plane ({x}, {y})")
        return x, y
    except Exception as e:
        logger.error(f"Error in pixel_to_coords: {str(e)}\n{traceback.format_exc()}")
        raise

def classify_anomaly(max_temp, area, temp_delta):
    """Classify anomaly type and severity based on temperature, area, and delta."""
    try:
        if max_temp > 90 and area > 1000:
            anomaly_type = "Severe Hot Spot"
            annotation = f"Critical defect likely in module or wiring (ΔT: {temp_delta:.1f}°C). Immediate inspection required."
        elif max_temp > 70 and area > 500:
            anomaly_type = "Hot Spot"
            annotation = f"Overheating issue, possibly due to dirt, shading, or defect (ΔT: {temp_delta:.1f}°C). Monitor closely."
        elif max_temp > 50 and area > 100:
            anomaly_type = "Warm Spot"
            annotation = f"Minor temperature elevation, may indicate early-stage issue (ΔT: {temp_delta:.1f}°C). Monitor periodically."
        else:
            anomaly_type = "Minor Anomaly"
            annotation = f"Small temperature rise, likely benign (ΔT: {temp_delta:.1f}°C). Monitor for changes."
        
        if max_temp > 90:
            severity = "Critical"
        elif max_temp > 70:
            severity = "Moderate"
        else:
            severity = "Minor"
        
        logger.debug(f"Classified anomaly: type={anomaly_type}, severity={severity}, max_temp={max_temp}, area={area}, temp_delta={temp_delta}")
        return anomaly_type, severity, annotation
    except Exception as e:
        logger.error(f"Error in classify_anomaly: {str(e)}\n{traceback.format_exc()}")
        raise

def extract_anomaly_image(full_image, center_x, center_y, window_size=100):
    """Extract a zoomed-in image around an anomaly."""
    logger.info(f"Extracting anomaly image at ({center_x}, {center_y})")
    try:
        if full_image is None or full_image.size == 0:
            raise ValueError("Full image is invalid or empty")
        
        height, width = full_image.shape[:2]
        half_size = window_size // 2
        
        x_start = max(0, center_x - half_size)
        x_end = min(width, center_x + half_size)
        y_start = max(0, center_y - half_size)
        y_end = min(height, center_y + half_size)
        
        anomaly_img = full_image[y_start:y_end, x_start:x_end].copy()
        if anomaly_img.size == 0:
            logger.warning(f"Empty anomaly image at ({center_x}, {center_y})")
            return None
        
        local_x = center_x - x_start
        local_y = center_y - y_start
        
        anomaly_img = cv2.cvtColor(anomaly_img, cv2.COLOR_RGB2BGR)
        cv2.circle(anomaly_img, (local_x, local_y), 5, (0, 0, 255), 2)
        anomaly_img = cv2.cvtColor(anomaly_img, cv2.COLOR_BGR2RGB)
        
        logger.info(f"Anomaly image extracted: shape={anomaly_img.shape}")
        return anomaly_img
    except Exception as e:
        logger.error(f"Error in extract_anomaly_image: {str(e)}\n{traceback.format_exc()}")
        raise

def compute_temperature_histogram(temp_array, bins=50, threshold=50.0):
    """Compute a histogram of temperatures below the anomaly threshold."""
    try:
        if temp_array is None or temp_array.size == 0:
            logger.warning("Temperature array is empty or None")
            return None, None
        
        valid_temps = temp_array[temp_array < threshold].flatten()
        if valid_temps.size == 0:
            logger.warning("No valid temperatures below threshold for histogram")
            return None, None
        
        hist, bin_edges = np.histogram(valid_temps, bins=bins, density=True)
        logger.debug(f"Computed temperature histogram: bins={len(hist)}, range=({bin_edges[0]:.1f}, {bin_edges[-1]:.1f})")
        return hist, bin_edges
    except Exception as e:
        logger.error(f"Error in compute_temperature_histogram: {str(e)}\n{traceback.format_exc()}")
        raise

def process_thermal_image(image_path, params):
    """Process R-JPEG using DJI Thermal SDK."""
    logger.info(f"Processing R-JPEG: {image_path}")
    try:
        img = cv2.imread(image_path)
        if img is None:
            logger.error(f"Failed to load R-JPEG: {image_path}")
            raise ValueError(f"Failed to load image: {image_path}")
        height, width = img.shape[:2]
        logger.info(f"R-JPEG dimensions: {width}x{height}")
        
        with open(image_path, 'rb') as f:
            jpeg_buffer = f.read()
        jpeg_buffer_array = (c_uint8 * len(jpeg_buffer)).from_buffer_copy(jpeg_buffer)
        
        handle = c_void_p()
        ret = lib.dirp_create(byref(handle))
        check_dirp_ret(ret, "dirp_create")
        
        try:
            ret = lib.dirp_set_emissivity(handle, c_float(params['emissivity']))
            check_dirp_ret(ret, "dirp_set_emissivity")
            ret = lib.dirp_set_distance(handle, c_float(params['distance']))
            check_dirp_ret(ret, "dirp_set_distance")
            ret = lib.dirp_set_humidity(handle, c_float(params['humidity']))
            check_dirp_ret(ret, "dirp_set_humidity")
            ret = lib.dirp_set_reflected_temperature(handle, c_float(params['ref_temp']))
            check_dirp_ret(ret, "dirp_set_reflected_temperature")
            
            ret = lib.dirp_process(handle, jpeg_buffer_array, c_uint32(len(jpeg_buffer)))
            check_dirp_ret(ret, "dirp_process")
            
            temp_buffer = (c_uint16 * (width * height))()
            ret = lib.dirp_get_temperature_data(handle, temp_buffer, c_int(width * height))
            check_dirp_ret(ret, "dirp_get_temperature_data")
            
            temp_array = np.ctypeslib.as_array(temp_buffer).reshape(height, width) / 10.0
            avg_temp = np.mean(temp_array[temp_array < 50])  # Average temp excluding anomalies
            hist, bin_edges = compute_temperature_histogram(temp_array)
            logger.info(f"Temperature array stats: min={temp_array.min():.2f}, max={temp_array.max():.2f}, avg (non-anomalous)={avg_temp:.2f}")
            
            rgb_buffer = (c_uint8 * (width * height * 3))()
            palette = DIRP_PSEUDO_COLOR.get(params['palette'], 2)
            ret = lib.dirp_get_thermal_image(handle, rgb_buffer, c_int(palette), c_int(0))
            check_dirp_ret(ret, "dirp_get_thermal_image")
            processed_img = np.ctypeslib.as_array(rgb_buffer).reshape(height, width, 3)
            processed_img = cv2.cvtColor(processed_img, cv2.COLOR_RGB2BGR)
            
            threshold_temp = 50.0
            anomaly_mask = temp_array > threshold_temp
            labeled_array, num_anomalies = measure.label(anomaly_mask, return_num=True)
            
            anomalies = []
            for region in measure.regionprops(labeled_array):
                if region.area > 50:
                    center_y, center_x = region.centroid
                    max_temp = np.max(temp_array[region.coords[:, 0], region.coords[:, 1]])
                    temp_delta = max_temp - avg_temp
                    anomaly_type, severity, annotation = classify_anomaly(max_temp, region.area, temp_delta)
                    anomaly_img = extract_anomaly_image(processed_img, int(center_x), int(center_y))
                    if anomaly_img is None:
                        continue
                    anomaly = {
                        'center_x': int(center_x),
                        'center_y': int(center_y),
                        'area': region.area,
                        'max_temp': max_temp,
                        'temp_delta': temp_delta,
                        'type': anomaly_type,
                        'severity': severity,
                        'annotation': annotation,
                        'image': anomaly_img
                    }
                    anomalies.append(anomaly)
            
            for anomaly in anomalies:
                cv2.circle(processed_img, (anomaly['center_x'], anomaly['center_y']), 10, (0, 0, 255), 2)
                cv2.putText(processed_img, f"{anomaly['max_temp']:.1f}°C",
                            (anomaly['center_x'] + 15, anomaly['center_y']),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            
            processed_img = cv2.cvtColor(processed_img, cv2.COLOR_BGR2RGB)
            if processed_img.size == 0 or processed_img.shape[2] != 3:
                logger.error(f"Processed image is invalid: shape={processed_img.shape}")
                raise ValueError("Processed image is invalid after R-JPEG processing")
            
            metadata = extract_metadata(image_path)
            metadata['parameters'] = params
            metadata['avg_temp'] = avg_temp
            metadata['temp_histogram'] = (hist, bin_edges)
            
            logger.info(f"Completed processing R-JPEG: {image_path}, found {len(anomalies)} anomalies")
            logger.info(f"Processed image shape: {processed_img.shape}, dtype: {processed_img.dtype}, min: {processed_img.min()}, max: {processed_img.max()}")
            return processed_img, anomalies, metadata
        
        finally:
            lib.dirp_destroy(handle)
    
    except Exception as e:
        logger.error(f"Error in process_thermal_image: {str(e)}\n{traceback.format_exc()}")
        raise

def process_geotiff(geotiff_path, params, kml_path=None, tfw_path=None, progress_callback=None):
    """Process GeoTIFF for thermal anomalies using tiled processing, with optional KML, TFW, and progress callback."""
    logger.info(f"Processing GeoTIFF: {geotiff_path}")
    try:
        # Load KML for georeferencing if provided
        kml_data = None
        use_kml = False
        if kml_path:
            kml_data = parse_kml(kml_path)
            # Check if KML has usable bounding box data
            if kml_data['bounds'] and all([kml_data['bounds']['north'], kml_data['bounds']['south'], 
                                           kml_data['bounds']['east'], kml_data['bounds']['west']]):
                use_kml = True
                logger.info(f"Using KML bounds for georeferencing: {kml_data['bounds']}")
            else:
                logger.warning("KML file lacks bounding box data (LatLonBox). Falling back to TFW if available.")
        
        # Load TFW as a fallback if KML is not usable
        tfw_data = None
        if tfw_path and not use_kml:
            tfw_data = load_tfw(tfw_path)
            logger.info("Using TFW for georeferencing since KML lacks bounding box data")
        elif tfw_path and use_kml:
            logger.info("Ignoring TFW file as KML is provided with valid bounding box data")
        elif not tfw_path and not use_kml:
            logger.warning("No usable KML or TFW provided for georeferencing")
        
        # Open GeoTIFF and process in tiles
        with rasterio.open(geotiff_path) as src:
            height, width = src.height, src.width
            logger.info(f"GeoTIFF dimensions: {width}x{height} pixels")
            tile_size = 1024  # Process 1024x1024 tiles

            # Downsample dimensions for processed_img (10% of original size)
            downsample_factor = 0.1
            display_width = int(width * downsample_factor)
            display_height = int(height * downsample_factor)
            logger.info(f"Downsampled dimensions for visualization: {display_width}x{display_height} pixels")
            
            # Compute average temperature (non-anomalous) incrementally
            logger.info("Computing average temperature (non-anomalous)...")
            avg_temp_sum = 0
            valid_pixels = 0
            bins = 50
            hist = np.zeros(bins, dtype=np.float64)
            bin_edges = np.linspace(0, 50, bins + 1)  # Temperatures from 0 to 50°C
            total_tiles = ((height + tile_size - 1) // tile_size) * ((width + tile_size - 1) // tile_size)
            tile_count = 0
            
            # Progress for average temperature calculation
            start_time = time.time()
            tile_positions = [(y, x) for y in range(0, height, tile_size) for x in range(0, width, tile_size)]
            for y, x in tile_positions:
                tile_count += 1
                tile_height = min(tile_size, height - y)
                tile_width = min(tile_size, width - x)
                window = Window(x, y, tile_width, tile_height)
                try:
                    temp_tile = src.read(1, window=window)
                    if temp_tile is None or temp_tile.size == 0:
                        logger.warning(f"Empty tile at position ({x}, {y})")
                        continue
                    # Scale temperature data
                    if temp_tile.max() > 1000:  # Likely Kelvin
                        logger.debug(f"Tile at ({x}, {y}) in Kelvin, converting to Celsius")
                        temp_tile = temp_tile - 273.15
                    elif temp_tile.max() < 100:  # Likely °C
                        temp_tile = temp_tile * 1.0
                    else:
                        temp_tile = temp_tile / 10.0
                    # Check for invalid values
                    if np.any(np.isnan(temp_tile)) or np.any(np.isinf(temp_tile)):
                        logger.warning(f"Tile at ({x}, {y}) contains NaN or Inf values")
                        continue
                    non_anomalous = temp_tile[temp_tile < 50]
                    if non_anomalous.size > 0:
                        avg_temp_sum += np.sum(non_anomalous)
                        valid_pixels += non_anomalous.size
                        # Accumulate histogram bins for this tile
                        tile_hist, _ = np.histogram(non_anomalous, bins=bin_edges, density=True)
                        hist += tile_hist * non_anomalous.size  # Weight by number of values
                except Exception as e:
                    logger.error(f"Error reading tile at ({x}, {y}): {str(e)}\n{traceback.format_exc()}")
                    raise
                # Update progress
                if progress_callback:
                    progress_callback(tile_count, total_tiles * 2, start_time)  # Multiply by 2 since we have two phases
            
            if valid_pixels == 0:
                logger.error("No valid pixels found for temperature calculation")
                raise ValueError("No valid pixels found for temperature calculation")
            avg_temp = avg_temp_sum / valid_pixels
            # Normalize histogram
            if valid_pixels > 0:
                hist = hist / valid_pixels
            logger.info(f"Average temperature (non-anomalous): {avg_temp:.2f}°C")
            
            # Initialize downsampled output image and anomalies
            logger.info("Initializing downsampled output image...")
            processed_img = np.zeros((display_height, display_width, 3), dtype=np.uint8)
            anomalies = []
            tile_count = total_tiles  # Continue counting for progress bar
            logger.info(f"Total tiles to process: {total_tiles}")
            
            # Progress for anomaly detection
            for y, x in tile_positions:
                tile_count += 1
                tile_height = min(tile_size, height - y)
                tile_width = min(tile_size, width - x)
                window = Window(x, y, tile_width, tile_height)
                
                try:
                    # Read tile data
                    logger.debug(f"Reading tile at ({x}, {y})...")
                    temp_tile = src.read(1, window=window)
                    if temp_tile is None or temp_tile.size == 0:
                        logger.warning(f"Empty tile at position ({x}, {y})")
                        continue
                    
                    # Scale temperature data
                    logger.debug(f"Scaling temperature data for tile at ({x}, {y})...")
                    if temp_tile.max() > 1000:  # Likely Kelvin
                        temp_tile = temp_tile - 273.15
                    elif temp_tile.max() < 100:  # Likely °C
                        temp_tile = temp_tile * 1.0
                    else:
                        temp_tile = temp_tile / 10.0
                    
                    # Check for invalid values
                    if np.any(np.isnan(temp_tile)) or np.any(np.isinf(temp_tile)):
                        logger.warning(f"Tile at ({x}, {y}) contains NaN or Inf values")
                        continue
                    
                    # Create visualization tile
                    logger.debug(f"Creating visualization for tile at ({x}, {y})...")
                    norm_temp = cv2.normalize(temp_tile, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
                    tile_img = cv2.applyColorMap(norm_temp, cv2.COLORMAP_INFERNO)
                    tile_img = cv2.cvtColor(tile_img, cv2.COLOR_BGR2RGB)
                    
                    # Downsample tile for placement in processed_img
                    tile_img_resized = cv2.resize(tile_img, (int(tile_width * downsample_factor), int(tile_height * downsample_factor)), interpolation=cv2.INTER_AREA)
                    display_x = int(x * downsample_factor)
                    display_y = int(y * downsample_factor)
                    display_tile_width = tile_img_resized.shape[1]
                    display_tile_height = tile_img_resized.shape[0]
                    
                    # Detect anomalies in tile
                    logger.debug(f"Detecting anomalies in tile at ({x}, {y})...")
                    threshold_temp = 50.0
                    anomaly_mask = temp_tile > threshold_temp
                    labeled_array, num_anomalies = measure.label(anomaly_mask, return_num=True)
                    
                    for region in measure.regionprops(labeled_array):
                        if region.area > 50:
                            center_y, center_x = region.centroid
                            global_x = int(center_x + x)
                            global_y = int(center_y + y)
                            # Adjust coordinates for downsampled image
                            display_x_anomaly = int(global_x * downsample_factor)
                            display_y_anomaly = int(global_y * downsample_factor)
                            max_temp = np.max(temp_tile[region.coords[:, 0], region.coords[:, 1]])
                            temp_delta = max_temp - avg_temp
                            anomaly_type, severity, annotation = classify_anomaly(max_temp, region.area, temp_delta)
                            anomaly_img = extract_anomaly_image(processed_img, display_x_anomaly, display_y_anomaly)
                            if anomaly_img is None:
                                continue
                            anomaly = {
                                'center_x': global_x,  # Store original coordinates
                                'center_y': global_y,
                                'display_x': display_x_anomaly,  # Store downsampled coordinates for visualization
                                'display_y': display_y_anomaly,
                                'area': region.area,
                                'max_temp': max_temp,
                                'temp_delta': temp_delta,
                                'type': anomaly_type,
                                'severity': severity,
                                'annotation': annotation,
                                'image': anomaly_img
                            }
                            # Add georeferenced coordinates
                            if use_kml:
                                # Use KML bounding box to convert pixel to Lat/Lon
                                lat, lon = pixel_to_latlon(global_x, global_y, kml_data['bounds'], width, height)
                                anomaly['latitude'] = lat
                                anomaly['longitude'] = lon
                                # Convert to State Plane for consistency (using Georgia West zone as a reference, but not critical since KML provides Lat/Lon)
                                state_x, state_y = transformer_to_state_plane.transform(lon, lat)
                                anomaly['coord_x'] = state_x
                                anomaly['coord_y'] = state_y
                                # Calculate area in square meters using KML bounds
                                lat_range = kml_data['bounds']['north'] - kml_data['bounds']['south']
                                lon_range = kml_data['bounds']['east'] - kml_data['bounds']['west']
                                # Approximate meters per degree (rough estimate, varies by latitude)
                                meters_per_deg_lat = 111139  # 1 degree latitude ≈ 111.139 km
                                meters_per_deg_lon = 111139 * np.cos(np.radians(lat))  # Adjust for longitude
                                pixel_area_m2 = region.area * (lon_range / width * meters_per_deg_lon) * (lat_range / height * meters_per_deg_lat)
                                anomaly['area_m2'] = pixel_area_m2
                            elif tfw_data:
                                # Fallback to TFW
                                state_x, state_y = pixel_to_coords(global_x, global_y, tfw_data)
                                anomaly['coord_x'] = state_x  # In State Plane feet (EPSG:6447)
                                anomaly['coord_y'] = state_y
                                # Convert to Lat/Lon
                                lon, lat = transformer_to_wgs84.transform(state_x, state_y)
                                anomaly['latitude'] = lat
                                anomaly['longitude'] = lon
                                # Calculate area in square meters
                                feet_to_meters = 0.3048006096  # 1 US Survey Foot = 0.3048006096 meters
                                pixel_area_m2 = region.area * (tfw_data['x_scale'] * abs(tfw_data['y_scale'])) * (feet_to_meters ** 2)
                                anomaly['area_m2'] = pixel_area_m2
                            else:
                                logger.warning("No usable KML or TFW provided for georeferencing")
                            anomalies.append(anomaly)
                    
                    # Mark anomalies on downsampled tile
                    logger.debug(f"Marking anomalies on tile at ({x}, {y})...")
                    tile_img_resized = cv2.cvtColor(tile_img_resized, cv2.COLOR_RGB2BGR)
                    for anomaly in anomalies:
                        if anomaly['center_x'] >= x and anomaly['center_x'] < x + tile_width and \
                           anomaly['center_y'] >= y and anomaly['center_y'] < y + tile_height:
                            local_x = anomaly['display_x'] - display_x
                            local_y = anomaly['display_y'] - display_y
                            # Ensure the local coordinates are within the downsampled tile bounds
                            if 0 <= local_x < display_tile_width and 0 <= local_y < display_tile_height:
                                cv2.circle(tile_img_resized, (local_x, local_y), 2, (0, 0, 255), 1)
                                cv2.putText(tile_img_resized, f"{anomaly['max_temp']:.1f}°C",
                                            (local_x + 5, local_y),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 255), 1)
                    
                    # Place tile in downsampled output image
                    logger.debug(f"Placing tile at ({display_x}, {display_y}) in downsampled output image...")
                    # Ensure the tile fits within the downsampled image bounds
                    display_x_end = min(display_x + display_tile_width, display_width)
                    display_y_end = min(display_y + display_tile_height, display_height)
                    tile_width_adjusted = display_x_end - display_x
                    tile_height_adjusted = display_y_end - display_y
                    if tile_width_adjusted > 0 and tile_height_adjusted > 0:
                        tile_img_adjusted = tile_img_resized[:tile_height_adjusted, :tile_width_adjusted]
                        processed_img[display_y:display_y+tile_height_adjusted, display_x:display_x+tile_width_adjusted] = cv2.cvtColor(tile_img_adjusted, cv2.COLOR_BGR2RGB)
                    
                except Exception as e:
                    logger.error(f"Error processing tile at ({x}, {y}): {str(e)}\n{traceback.format_exc()}")
                    raise
                # Update progress
                if progress_callback:
                    progress_callback(tile_count, total_tiles * 2, start_time)
            
            # Validate processed image
            logger.info("Validating processed image...")
            if processed_img is None or processed_img.size == 0 or processed_img.shape[2] != 3:
                logger.error(f"Processed image is invalid: shape={processed_img.shape if processed_img is not None else 'None'}")
                raise ValueError("Processed image is invalid after GeoTIFF processing")
            
            metadata = extract_geotiff_metadata(geotiff_path)
            if kml_data:
                metadata['kml_data'] = kml_data
            if tfw_data:
                metadata['tfw_data'] = tfw_data
            metadata['parameters'] = params
            metadata['avg_temp'] = avg_temp
            metadata['temp_histogram'] = (hist, bin_edges)
            
            logger.info(f"Completed processing GeoTIFF: {geotiff_path}, found {len(anomalies)} anomalies")
            logger.info(f"Processed image shape: {processed_img.shape}, dtype: {processed_img.dtype}, min: {processed_img.min()}, max: {processed_img.max()}")
            return processed_img, anomalies, metadata
    
    except Exception as e:
        logger.error(f"Error in process_geotiff: {str(e)}\n{traceback.format_exc()}")
        raise