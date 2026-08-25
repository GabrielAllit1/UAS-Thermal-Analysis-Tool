import cv2
import numpy as np
import pandas as pd
from datetime import datetime
import os
import logging
from lxml import etree
import pykml.parser
from pyproj import Transformer
import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend for thread safety
import matplotlib.pyplot as plt
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.platypus import Table, TableStyle

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_histogram_image(hist, bin_edges, output_path):
    """Generate a histogram image for temperature distribution."""
    plt.figure(figsize=(4, 2))
    plt.bar(bin_edges[:-1], hist, width=np.diff(bin_edges), align='edge', edgecolor='black')
    plt.title("Temperature Distribution (Non-Anomalous)", fontsize=10)
    plt.xlabel("Temperature (°C)", fontsize=8)
    plt.ylabel("Density", fontsize=8)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, format='png', dpi=150)
    plt.close()

def generate_pie_chart(type_counts, output_path):
    """Generate a pie chart for anomaly type distribution."""
    plt.figure(figsize=(4, 4))
    labels = list(type_counts.keys())
    sizes = list(type_counts.values())
    plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140, textprops={'fontsize': 8})
    plt.title("Anomaly Type Distribution", fontsize=10)
    plt.savefig(output_path, format='png', dpi=150, bbox_inches='tight')
    plt.close()

def generate_severity_bar_chart(severity_counts, output_path):
    """Generate a bar chart for severity distribution."""
    plt.figure(figsize=(4, 2))
    labels = list(severity_counts.keys())
    counts = list(severity_counts.values())
    plt.bar(labels, counts, color=['#ff9999', '#ffcc99', '#99ff99'])  # Soft red, orange, green
    plt.title("Severity Distribution", fontsize=10)
    plt.xlabel("Severity", fontsize=8)
    plt.ylabel("Count", fontsize=8)
    plt.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(output_path, format='png', dpi=150)
    plt.close()

def generate_kml(anomalies, output_path, kml_path=None, tfw_path=None):
    """Generate a KML file with anomaly placemarks in Lat/Lon."""
    logger.info(f"Generating KML file: {output_path}")
    kml = etree.Element("kml", xmlns="http://www.opengis.net/kml/2.2")
    document = etree.SubElement(kml, "Document")
    
    # Add styles for placemarks based on severity
    for severity, color in [("Critical", "ff0000ff"), ("Moderate", "ff00ffff"), ("Minor", "ff00ff00")]:  # Red, Yellow, Green
        style = etree.SubElement(document, "Style", id=f"{severity}Style")
        icon_style = etree.SubElement(style, "IconStyle")
        etree.SubElement(icon_style, "color").text = color
        icon = etree.SubElement(icon_style, "Icon")
        etree.SubElement(icon, "href").text = "http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png"
    
    for i, anomaly in enumerate(anomalies):
        if 'latitude' not in anomaly or 'longitude' not in anomaly:
            logger.warning(f"Anomaly {i+1} has no Lat/Lon coordinates, skipping placemark")
            continue
        lon, lat = anomaly['longitude'], anomaly['latitude']
        placemark = etree.SubElement(document, "Placemark")
        etree.SubElement(placemark, "name").text = f"Anomaly {i+1}"
        description = (f"Type: {anomaly['type']}\nSeverity: {anomaly['severity']}\n"
                      f"Max Temp: {anomaly['max_temp']:.1f}°C\n"
                      f"ΔT: {anomaly['temp_delta']:.1f}°C\n"
                      f"Area: {anomaly['area_m2']:.2f} m²\n"
                      f"Annotation: {anomaly['annotation']}")
        etree.SubElement(placemark, "description").text = description
        etree.SubElement(placemark, "styleUrl").text = f"#{anomaly['severity']}Style"
        point = etree.SubElement(placemark, "Point")
        coordinates = f"{lon},{lat},0"
        etree.SubElement(point, "coordinates").text = coordinates
    
    with open(output_path, 'wb') as f:
        f.write(etree.tostring(kml, pretty_print=True, xml_declaration=True, encoding='UTF-8'))
    logger.info(f"KML file generated: {output_path}")

def generate_batch_pdf_report(output_path, results):
    """Generate a PDF report for batch R-JPEG processing."""
    logger.info(f"Generating batch PDF report: {output_path}")
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter
    
    # Title page
    c.setFont("Times-Bold", 20)
    c.drawCentredString(width / 2, height - 0.8 * inch, "Thermal Analysis Batch Report - DJI Mavic 3T")
    c.setFont("Times-Roman", 12)
    c.drawString(1 * inch, height - 1.5 * inch, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    c.drawString(1 * inch, height - 2 * inch, f"Total Images Processed: {len(results)}")
    total_anomalies = sum(len(result['anomalies']) for result in results)
    c.drawString(1 * inch, height - 2.5 * inch, f"Total Anomalies Detected: {total_anomalies}")
    
    # Footer
    c.setFont("Times-Roman", 8)
    c.drawString(1 * inch, 0.5 * inch, "Thermal Analysis | Contact: MRDrones@mastec.com | Page 1")
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0.5, 0.5, 0.5)  # Gray line
    c.line(1 * inch, 0.6 * inch, width - 1 * inch, 0.6 * inch)  # Footer separator
    c.setStrokeColorRGB(0, 0, 0)  # Reset to black
    c.showPage()
    
    # One page per image
    page_num = 2
    for result in results:
        image_path = result['image_path']
        processed_image = result['processed_image']
        anomalies = result['anomalies']
        metadata = result['metadata']
        
        # Header
        c.setFont("Times-Bold", 14)
        c.drawString(1 * inch, height - 0.4 * inch, f"R-JPEG: {os.path.basename(image_path)}")
        c.setLineWidth(0.5)
        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        c.line(1 * inch, height - 0.5 * inch, width - 1 * inch, height - 0.5 * inch)  # Underline
        c.setStrokeColorRGB(0, 0, 0)
        
        # Content
        c.setFont("Times-Roman", 10)
        c.drawString(1 * inch, height - 1 * inch, "Original R-JPEG:")
        orig_img = cv2.imread(image_path)
        if orig_img is None:
            logger.error(f"Failed to load original image: {image_path}")
            raise ValueError(f"Failed to load original image: {image_path}")
        orig_img = cv2.cvtColor(orig_img, cv2.COLOR_BGR2RGB)
        temp_orig_path = os.path.join(os.path.dirname(output_path), "temp_orig.jpg")
        if not cv2.imwrite(temp_orig_path, orig_img):
            logger.error(f"Failed to save temp_orig.jpg at {temp_orig_path}")
            raise ValueError(f"Failed to save temp_orig.jpg at {temp_orig_path}")
        c.drawImage(temp_orig_path, 1 * inch, height - 4 * inch, 3 * inch, 2 * inch)
        
        c.drawString(4.5 * inch, height - 1 * inch, "Processed Image with Anomalies:")
        temp_processed_path = os.path.join(os.path.dirname(output_path), "temp_processed.jpg")
        if not cv2.imwrite(temp_processed_path, processed_image):
            logger.error(f"Failed to save temp_processed.jpg at {temp_processed_path}")
            raise ValueError(f"Failed to save temp_processed.jpg at {temp_processed_path}")
        c.drawImage(temp_processed_path, 4.5 * inch, height - 4 * inch, 3 * inch, 2 * inch)
        
        c.drawString(1 * inch, height - 4.5 * inch, "Metadata:")
        c.setFont("Times-Roman", 9)
        y_pos = height - 4.8 * inch
        for key, value in list(metadata.items())[:10]:
            c.drawString(1.2 * inch, y_pos, f"{key}: {value}")
            y_pos -= 0.2 * inch
        
        c.setFont("Times-Bold", 10)
        c.drawString(1 * inch, height - 6.5 * inch, f"Anomalies Detected: {len(anomalies)}")
        c.setFont("Times-Roman", 9)
        y_pos = height - 6.8 * inch
        for i, anomaly in enumerate(anomalies):
            text = f"Anomaly {i+1}: Center at ({anomaly['center_x']}, {anomaly['center_y']}), "
            text += f"Area: {anomaly['area']:.1f} px, Max Temp: {anomaly['max_temp']:.1f}°C"
            c.drawString(1.2 * inch, y_pos, text)
            y_pos -= 0.2 * inch
            if y_pos < 1 * inch:
                c.showPage()
                page_num += 1
                y_pos = height - 1 * inch
                c.setFont("Times-Roman", 9)
        
        # Footer
        c.setFont("Times-Roman", 8)
        c.drawString(1 * inch, 0.5 * inch, f"Thermal Analysis | Contact: MRDrones@mastec.com | Page {page_num}")
        c.setLineWidth(0.5)
        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        c.line(1 * inch, 0.6 * inch, width - 1 * inch, 0.6 * inch)  # Footer separator
        c.setStrokeColorRGB(0, 0, 0)
        c.showPage()
        page_num += 1
    
    c.save()
    for temp_file in [temp_orig_path, temp_processed_path]:
        if os.path.exists(temp_file):
            os.remove(temp_file)
    logger.info(f"Batch PDF report generated: {output_path}")

def generate_batch_csv_report(output_path, results):
    """Generate a CSV report for batch R-JPEG processing."""
    logger.info(f"Generating batch CSV report: {output_path}")
    data = []
    for result in results:
        image_path = result['image_path']
        for i, anomaly in enumerate(result['anomalies']):
            data.append({
                'Image': os.path.basename(image_path),
                'Anomaly_ID': i + 1,
                'Center_X': anomaly['center_x'],
                'Center_Y': anomaly['center_y'],
                'Area': anomaly['area'],
                'Max_Temperature': anomaly['max_temp'],
                'Type': anomaly.get('type', 'N/A'),
                'Severity': anomaly.get('severity', 'N/A'),
                'Annotation': anomaly.get('annotation', 'N/A'),
                'Coord_X': anomaly.get('coord_x', 'N/A'),
                'Coord_Y': anomaly.get('coord_y', 'N/A'),
                'Latitude': anomaly.get('latitude', 'N/A'),
                'Longitude': anomaly.get('longitude', 'N/A'),
                'Temp_Delta': anomaly.get('temp_delta', 'N/A'),
                'Area_m2': anomaly.get('area_m2', 'N/A')
            })
    
    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False)
    logger.info(f"Batch CSV report generated: {output_path}")

def generate_geotiff_pdf_report(output_path, result, kml_path=None, tfw_path=None):
    """Generate a detailed PDF report for a single GeoTIFF with optional KML and TFW."""
    logger.info(f"Generating GeoTIFF PDF report: {output_path}")
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter
    
    # Page 1: Cover Page
    c.setFont("Times-Bold", 24)
    c.drawCentredString(width / 2, height - 0.8 * inch, "Thermal Analysis Report")
    c.setFont("Times-Bold", 16)
    c.drawCentredString(width / 2, height - 1.3 * inch, "De Soto III Solar Farm - DJI Mavic 3T")
    
    c.setFont("Times-Roman", 12)
    c.drawString(1 * inch, height - 2.5 * inch, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    c.drawString(1 * inch, height - 3 * inch, "Inspection Date: 2024-02-01")
    c.drawString(1 * inch, height - 3.5 * inch, "Location: De Soto III Solar Farm, GA, USA")
    c.drawString(1 * inch, height - 4 * inch, f"GeoTIFF Processed: 1")
    c.drawString(1 * inch, height - 4.5 * inch, f"Anomalies Detected: {len(result['anomalies'])}")
    
    # Summary
    c.setFont("Times-Bold", 14)
    c.drawString(1 * inch, height - 5.5 * inch, "Summary:")
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0.5, 0.5, 0.5)
    c.line(1 * inch, height - 5.6 * inch, width - 1 * inch, height - 5.6 * inch)  # Section separator
    c.setStrokeColorRGB(0, 0, 0)
    c.setFont("Times-Roman", 10)
    summary_text = (f"This report details the thermal analysis of De Soto III Solar Farm, conducted on 2024-02-01 using a DJI Mavic 3T drone. "
                    f"{len(result['anomalies'])} anomalies were detected, with {sum(1 for a in result['anomalies'] if a['severity'] == 'Critical')} classified as critical. "
                    "Immediate action is recommended for critical anomalies.")
    y_pos = height - 6.5 * inch
    for line in summary_text.split('. '):
        c.drawString(1 * inch, y_pos, line.strip() + ('.' if line.strip() else ''))
        y_pos -= 0.3 * inch
    
    # Footer
    c.setFont("Times-Roman", 8)
    c.drawString(1 * inch, 0.5 * inch, "Thermal Analysis | Contact: MRDrones@mastec.com | Page 1")
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0.5, 0.5, 0.5)
    c.line(1 * inch, 0.6 * inch, width - 1 * inch, 0.6 * inch)  # Footer separator
    c.setStrokeColorRGB(0, 0, 0)
    c.showPage()
    
    # Page 2: Overview
    page_num = 2
    image_path = result['image_path']
    processed_image = result['processed_image']
    anomalies = result['anomalies']
    metadata = result['metadata']
    params = metadata.get('parameters', {})
    avg_temp = metadata.get('avg_temp', 0)
    
    # Header
    c.setFont("Times-Bold", 18)
    c.drawString(1 * inch, height - 0.4 * inch, f"GeoTIFF: {os.path.basename(image_path)[:30]}...")
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0.5, 0.5, 0.5)
    c.line(1 * inch, height - 0.5 * inch, width - 1 * inch, height - 0.5 * inch)  # Underline
    c.setStrokeColorRGB(0, 0, 0)
    
    # Processed GeoTIFF with Anomalies
    c.setFont("Times-Bold", 12)
    c.drawString(1.1 * inch, height - 1.1 * inch, "Processed GeoTIFF with Anomalies")
    c.setFont("Times-Roman", 10)
    y_pos = height - 1.5 * inch
    
    if processed_image is None or processed_image.size == 0 or len(processed_image.shape) != 3 or processed_image.shape[2] != 3:
        logger.error(f"Processed image is invalid: shape={processed_image.shape if processed_image is not None else 'None'}")
        raise ValueError("Processed image is invalid before saving for report")
    
    max_width = 6 * inch
    max_height = 4 * inch
    img_height, img_width = processed_image.shape[:2]
    aspect_ratio = img_width / img_height
    if img_width / img_height > max_width / max_height:
        display_width = max_width
        display_height = max_width / aspect_ratio
    else:
        display_height = max_height
        display_width = max_height * aspect_ratio
    
    temp_processed_path = os.path.join(os.path.dirname(output_path), "temp_processed.jpg")
    logger.info(f"Saving processed image to {temp_processed_path}")
    success = cv2.imwrite(temp_processed_path, processed_image)
    if not success:
        logger.error(f"Failed to save temp_processed.jpg at {temp_processed_path}. Attempting fallback with smaller image.")
        placeholder = np.zeros((100, 100, 3), dtype=np.uint8)
        placeholder[:] = (255, 0, 0)
        cv2.putText(placeholder, "Image Save Failed", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        if not cv2.imwrite(temp_processed_path, placeholder):
            logger.error(f"Fallback save also failed at {temp_processed_path}.")
            raise ValueError(f"Failed to save temp_processed.jpg at {temp_processed_path}, even with fallback")
        logger.info(f"Fallback image saved at {temp_processed_path}")
    
    if not os.path.exists(temp_processed_path):
        logger.error(f"temp_processed.jpg not found at {temp_processed_path} after saving")
        raise ValueError(f"temp_processed.jpg not found at {temp_processed_path} after saving")
    
    logger.info(f"temp_processed.jpg saved successfully, size: {os.path.getsize(temp_processed_path)} bytes")
    c.drawImage(temp_processed_path, 1 * inch, height - 5.5 * inch, display_width, display_height)
    
    # Environmental Parameters
    c.setFont("Times-Bold", 12)
    c.drawString(1.1 * inch, height - 5.9 * inch, "Environmental Parameters")
    c.setFont("Times-Roman", 9)
    y_pos = height - 6.3 * inch
    param_items = [
        f"Emissivity: {params.get('emissivity', 'N/A')}",
        f"Distance: {params.get('distance', 'N/A')} m",
        f"Humidity: {params.get('humidity', 'N/A')}",
        f"Reflected Temp: {params.get('ref_temp', 'N/A')}°C",
        f"Average Site Temp (non-anomalous): {avg_temp:.1f}°C",
        "Weather Impact: Sunny conditions may elevate temperature readings by 1-2°C."
    ]
    for item in param_items:
        c.drawString(1.2 * inch, y_pos, item)
        y_pos -= 0.2 * inch
    
    # GeoTIFF Metadata
    c.setFont("Times-Bold", 12)
    c.drawString(1.1 * inch, y_pos - 0.2 * inch, "GeoTIFF Metadata")
    y_pos -= 0.5 * inch
    geotiff_metadata = [
        f"CRS: {metadata.get('CRS', 'N/A')}",
        f"Dimensions: {metadata.get('Width', 'N/A')} x {metadata.get('Height', 'N/A')} pixels",
        f"Bands: {metadata.get('Bands', 'N/A')}",
        f"Resolution: {metadata.get('Resolution', (0, 0))[0]:.6f} x {metadata.get('Resolution', (0, 0))[1]:.6f} units/pixel",
        f"Compression: {metadata.get('Compression', 'N/A')}"
    ]
    for item in geotiff_metadata:
        c.drawString(1.2 * inch, y_pos, item)
        y_pos -= 0.2 * inch
    
    # KML Metadata
    if 'kml_data' in metadata:
        c.setFont("Times-Bold", 12)
        c.drawString(1.1 * inch, y_pos - 0.2 * inch, "KML Metadata")
        y_pos -= 0.5 * inch
        kml_data = metadata['kml_data']
        bounds = kml_data.get('bounds', {})
        kml_metadata_items = [
            f"Bounding Box: N {bounds.get('north', 'N/A')}, S {bounds.get('south', 'N/A')}, E {bounds.get('east', 'N/A')}, W {bounds.get('west', 'N/A')}",
            f"Placemarks Found: {len(kml_data.get('placemarks', []))}"
        ]
        for item in kml_metadata_items:
            c.drawString(1.2 * inch, y_pos, item)
            y_pos -= 0.2 * inch
        for key, value in kml_data.get('metadata', {}).items():
            c.drawString(1.2 * inch, y_pos, f"{key}: {value}")
            y_pos -= 0.2 * inch
    
    # Footer
    c.setFont("Times-Roman", 8)
    c.drawString(1 * inch, 0.5 * inch, f"Thermal Analysis | Contact: MRDrones@mastec.com | Page {page_num}")
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0.5, 0.5, 0.5)
    c.line(1 * inch, 0.6 * inch, width - 1 * inch, 0.6 * inch)  # Footer separator
    c.setStrokeColorRGB(0, 0, 0)
    c.showPage()
    page_num += 1
    
    # Page 3: Anomaly Statistics
    c.setFont("Times-Bold", 18)
    c.drawString(1 * inch, height - 0.4 * inch, "Anomaly Statistics")
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0.5, 0.5, 0.5)
    c.line(1 * inch, height - 0.5 * inch, width - 1 * inch, height - 0.5 * inch)  # Underline
    c.setStrokeColorRGB(0, 0, 0)
    
    # Distribution of Anomaly Types (Text)
    c.setFont("Times-Bold", 12)
    c.drawString(1.1 * inch, height - 1.1 * inch, "Distribution of Anomaly Types")
    c.setFont("Times-Roman", 9)
    y_pos = height - 1.5 * inch
    type_counts = {}
    for anomaly in anomalies:
        atype = anomaly['type']
        type_counts[atype] = type_counts.get(atype, 0) + 1
    for atype, count in type_counts.items():
        c.drawString(1.2 * inch, y_pos, f"{atype}: {count} anomalies")
        y_pos -= 0.2 * inch
    
    # Pie Chart for Anomaly Types
    pie_path = os.path.join(os.path.dirname(output_path), "temp_pie_chart.png")
    generate_pie_chart(type_counts, pie_path)
    c.drawImage(pie_path, 1 * inch, y_pos - 2.5 * inch, 3 * inch, 3 * inch)
    y_pos -= 2.8 * inch
    
    # Severity Distribution (Bar Chart)
    c.setFont("Times-Bold", 12)
    c.drawString(1.1 * inch, y_pos - 0.2 * inch, "Severity Distribution")
    severity_counts = {'Critical': 0, 'Moderate': 0, 'Minor': 0}
    for anomaly in anomalies:
        severity = anomaly['severity']
        if severity in severity_counts:
            severity_counts[severity] += 1
    bar_path = os.path.join(os.path.dirname(output_path), "temp_severity_bar.png")
    generate_severity_bar_chart(severity_counts, bar_path)
    c.drawImage(bar_path, 1 * inch, y_pos - 2.5 * inch, 4 * inch, 2 * inch)
    y_pos -= 2.8 * inch
    
    # Temperature Histogram
    hist, bin_edges = metadata.get('temp_histogram', (None, None))
    if hist is not None:
        c.setFont("Times-Bold", 12)
        c.drawString(1.1 * inch, y_pos - 0.2 * inch, "Temperature Distribution")
        temp_hist_path = os.path.join(os.path.dirname(output_path), "temp_histogram.png")
        generate_histogram_image(hist, bin_edges, temp_hist_path)
        c.drawImage(temp_hist_path, 1 * inch, y_pos - 2.5 * inch, 4 * inch, 2 * inch)
        y_pos -= 2.8 * inch
    
    # Footer
    c.setFont("Times-Roman", 8)
    c.drawString(1 * inch, 0.5 * inch, f"Thermal Analysis | Contact: MRDrones@mastec.com | Page {page_num}")
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0.5, 0.5, 0.5)
    c.line(1 * inch, 0.6 * inch, width - 1 * inch, 0.6 * inch)  # Footer separator
    c.setStrokeColorRGB(0, 0, 0)
    c.showPage()
    page_num += 1
    
    # Page 4: Anomaly Details - Part 1 (Core Details)
    c.setFont("Times-Bold", 18)
    c.drawString(1 * inch, height - 0.4 * inch, "Anomaly Details - Core Information")
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0.5, 0.5, 0.5)
    c.line(1 * inch, height - 0.5 * inch, width - 1 * inch, height - 0.5 * inch)  # Underline
    c.setStrokeColorRGB(0, 0, 0)
    
    # Create the first table for core anomaly details
    table_data = [['ID', 'Priority', 'Type', 'Severity', 'Max Temp (°C)', 'ΔT (°C)', 'Area (px)', 'Area (m²)', 'Coordinates', 'Lat', 'Lon']]
    for i, anomaly in enumerate(anomalies):
        priority = 1 if anomaly['severity'] == 'Critical' else (2 if anomaly['severity'] == 'Moderate' else 3)
        table_data.append([
            str(i + 1),
            str(priority),
            anomaly['type'],
            anomaly['severity'],
            f"{anomaly['max_temp']:.1f}",
            f"{anomaly['temp_delta']:.1f}",
            f"{anomaly['area']:.1f}",
            f"{anomaly.get('area_m2', 'N/A'):.2f}",
            f"({anomaly['display_x']}, {anomaly['display_y']})",
            f"{anomaly.get('latitude', 'N/A'):.6f}",
            f"{anomaly.get('longitude', 'N/A'):.6f}",
        ])
    
    # Define column widths for the first table (11 columns)
    available_width = 6.5 * inch  # Page width (8.5 inches) - 2 * 1-inch margins
    col_widths = [0.4 * inch, 0.5 * inch, 0.7 * inch, 0.6 * inch, 0.7 * inch, 0.6 * inch, 0.6 * inch, 0.6 * inch, 0.8 * inch, 0.5 * inch, 0.5 * inch]
    total_width = sum(col_widths)
    if total_width > available_width:
        scale_factor = available_width / total_width
        col_widths = [w * scale_factor for w in col_widths]
        logger.info(f"Scaled column widths by factor {scale_factor:.2f} to fit within {available_width/inch:.1f} inches")
    
    table = Table(table_data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
        ('GRID', (0, 0), (-1, -1), 0.5, (0, 0, 0))
    ]))
    
    table_width = sum(col_widths)
    table_height = len(table_data) * 0.35 * inch  # Adjusted row height
    if table_height > height - 2 * inch:
        rows_per_page = int((height - 2 * inch) / (0.35 * inch))
        for start_row in range(0, len(table_data), rows_per_page):
            end_row = min(start_row + rows_per_page, len(table_data))
            sub_table_data = table_data[start_row:end_row]
            sub_table = Table(sub_table_data, colWidths=col_widths)
            sub_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
                ('GRID', (0, 0), (-1, -1), 0.5, (0, 0, 0))
            ]))
            sub_table.wrapOn(c, table_width, height - 2 * inch)
            sub_table.drawOn(c, 1 * inch, height - 1.5 * inch - (end_row - start_row) * 0.35 * inch)
            c.setFont("Times-Roman", 8)
            c.drawString(1 * inch, 0.5 * inch, f"Thermal Analysis | Contact: MRDrones@mastec.com | Page {page_num}")
            c.setLineWidth(0.5)
            c.setStrokeColorRGB(0.5, 0.5, 0.5)
            c.line(1 * inch, 0.6 * inch, width - 1 * inch, 0.6 * inch)  # Footer separator
            c.setStrokeColorRGB(0, 0, 0)
            c.showPage()
            page_num += 1
    else:
        table.wrapOn(c, table_width, table_height)
        table.drawOn(c, 1 * inch, height - 1.5 * inch - table_height)
        c.setFont("Times-Roman", 8)
        c.drawString(1 * inch, 0.5 * inch, f"Thermal Analysis | Contact: MRDrones@mastec.com | Page {page_num}")
        c.setLineWidth(0.5)
        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        c.line(1 * inch, 0.6 * inch, width - 1 * inch, 0.6 * inch)  # Footer separator
        c.setStrokeColorRGB(0, 0, 0)
        c.showPage()
        page_num += 1
    
    # Page 5: Anomaly Details - Part 2 (Maintenance Actions)
    c.setFont("Times-Bold", 18)
    c.drawString(1 * inch, height - 0.4 * inch, "Anomaly Details - Maintenance Actions")
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0.5, 0.5, 0.5)
    c.line(1 * inch, height - 0.5 * inch, width - 1 * inch, height - 0.5 * inch)  # Underline
    c.setStrokeColorRGB(0, 0, 0)
    
    # Create the second table for Maintenance Action
    table_data = [['ID', 'Maintenance Action']]
    for i, anomaly in enumerate(anomalies):
        maintenance_action = {
            'Severe Hot Spot': "Inspect and replace faulty module or wiring immediately.",
            'Hot Spot': "Clean panel surface, check for shading or defects, schedule repair.",
            'Warm Spot': "Monitor panel performance, schedule cleaning if needed.",
            'Minor Anomaly': "Log for future monitoring, no immediate action required."
        }.get(anomaly['type'], "Monitor and reassess during next inspection.")
        table_data.append([
            str(i + 1),
            maintenance_action
        ])
    
    # Define column widths for the second table (2 columns)
    col_widths = [0.5 * inch, 6.0 * inch]  # Wide column for Maintenance Action
    total_width = sum(col_widths)
    if total_width > available_width:
        scale_factor = available_width / total_width
        col_widths = [w * scale_factor for w in col_widths]
        logger.info(f"Scaled column widths by factor {scale_factor:.2f} to fit within {available_width/inch:.1f} inches")
    
    table = Table(table_data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),  # Center ID column
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),   # Left-align Maintenance Action
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
        ('GRID', (0, 0), (-1, -1), 0.5, (0, 0, 0))
    ]))
    
    table_width = sum(col_widths)
    table_height = len(table_data) * 0.35 * inch
    if table_height > height - 2 * inch:
        rows_per_page = int((height - 2 * inch) / (0.35 * inch))
        for start_row in range(0, len(table_data), rows_per_page):
            end_row = min(start_row + rows_per_page, len(table_data))
            sub_table_data = table_data[start_row:end_row]
            sub_table = Table(sub_table_data, colWidths=col_widths)
            sub_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
                ('GRID', (0, 0), (-1, -1), 0.5, (0, 0, 0))
            ]))
            sub_table.wrapOn(c, table_width, height - 2 * inch)
            sub_table.drawOn(c, 1 * inch, height - 1.5 * inch - (end_row - start_row) * 0.35 * inch)
            c.setFont("Times-Roman", 8)
            c.drawString(1 * inch, 0.5 * inch, f"Thermal Analysis | Contact: MRDrones@mastec.com | Page {page_num}")
            c.setLineWidth(0.5)
            c.setStrokeColorRGB(0.5, 0.5, 0.5)
            c.line(1 * inch, 0.6 * inch, width - 1 * inch, 0.6 * inch)  # Footer separator
            c.setStrokeColorRGB(0, 0, 0)
            c.showPage()
            page_num += 1
    else:
        table.wrapOn(c, table_width, table_height)
        table.drawOn(c, 1 * inch, height - 1.5 * inch - table_height)
        c.setFont("Times-Roman", 8)
        c.drawString(1 * inch, 0.5 * inch, f"Thermal Analysis | Contact: MRDrones@mastec.com | Page {page_num}")
        c.setLineWidth(0.5)
        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        c.line(1 * inch, 0.6 * inch, width - 1 * inch, 0.6 * inch)  # Footer separator
        c.setStrokeColorRGB(0, 0, 0)
        c.showPage()
        page_num += 1
    
    # Page 6: Anomaly Details - Part 3 (Annotations)
    c.setFont("Times-Bold", 18)
    c.drawString(1 * inch, height - 0.4 * inch, "Anomaly Details - Annotations")
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0.5, 0.5, 0.5)
    c.line(1 * inch, height - 0.5 * inch, width - 1 * inch, height - 0.5 * inch)  # Underline
    c.setStrokeColorRGB(0, 0, 0)
    
    # Create the third table for Annotation
    table_data = [['ID', 'Annotation']]
    for i, anomaly in enumerate(anomalies):
        table_data.append([
            str(i + 1),
            anomaly['annotation']
        ])
    
    # Define column widths for the third table (2 columns)
    col_widths = [0.5 * inch, 6.0 * inch]  # Wide column for Annotation
    total_width = sum(col_widths)
    if total_width > available_width:
        scale_factor = available_width / total_width
        col_widths = [w * scale_factor for w in col_widths]
        logger.info(f"Scaled column widths by factor {scale_factor:.2f} to fit within {available_width/inch:.1f} inches")
    
    table = Table(table_data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),  # Center ID column
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),   # Left-align Annotation
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
        ('GRID', (0, 0), (-1, -1), 0.5, (0, 0, 0))
    ]))
    
    table_width = sum(col_widths)
    table_height = len(table_data) * 0.35 * inch
    if table_height > height - 2 * inch:
        rows_per_page = int((height - 2 * inch) / (0.35 * inch))
        for start_row in range(0, len(table_data), rows_per_page):
            end_row = min(start_row + rows_per_page, len(table_data))
            sub_table_data = table_data[start_row:end_row]
            sub_table = Table(sub_table_data, colWidths=col_widths)
            sub_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('ALIGN', (0, 0), (0, -1), 'CENTER'),
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),
                ('GRID', (0, 0), (-1, -1), 0.5, (0, 0, 0))
            ]))
            sub_table.wrapOn(c, table_width, height - 2 * inch)
            sub_table.drawOn(c, 1 * inch, height - 1.5 * inch - (end_row - start_row) * 0.35 * inch)
            c.setFont("Times-Roman", 8)
            c.drawString(1 * inch, 0.5 * inch, f"Thermal Analysis | Contact: MRDrones@mastec.com | Page {page_num}")
            c.setLineWidth(0.5)
            c.setStrokeColorRGB(0.5, 0.5, 0.5)
            c.line(1 * inch, 0.6 * inch, width - 1 * inch, 0.6 * inch)  # Footer separator
            c.setStrokeColorRGB(0, 0, 0)
            c.showPage()
            page_num += 1
    else:
        table.wrapOn(c, table_width, table_height)
        table.drawOn(c, 1 * inch, height - 1.5 * inch - table_height)
        c.setFont("Times-Roman", 8)
        c.drawString(1 * inch, 0.5 * inch, f"Thermal Analysis | Contact: MRDrones@mastec.com | Page {page_num}")
        c.setLineWidth(0.5)
        c.setStrokeColorRGB(0.5, 0.5, 0.5)
        c.line(1 * inch, 0.6 * inch, width - 1 * inch, 0.6 * inch)  # Footer separator
        c.setStrokeColorRGB(0, 0, 0)
        c.showPage()
        page_num += 1
    
    # Page 7+: Anomaly Images (2 per page with details)
    c.setFont("Times-Bold", 18)
    c.drawString(1 * inch, height - 0.4 * inch, "Anomaly Images")
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0.5, 0.5, 0.5)
    c.line(1 * inch, height - 0.5 * inch, width - 1 * inch, height - 0.5 * inch)  # Underline
    c.setStrokeColorRGB(0, 0, 0)
    
    y_pos = height - 1.2 * inch
    images_per_page = 0
    for i, anomaly in enumerate(anomalies):
        # Start a new page if we've reached 2 images
        if images_per_page >= 2:
            c.setFont("Times-Roman", 8)
            c.drawString(1 * inch, 0.5 * inch, f"Thermal Analysis | Contact: MRDrones@mastec.com | Page {page_num}")
            c.setLineWidth(0.5)
            c.setStrokeColorRGB(0.5, 0.5, 0.5)
            c.line(1 * inch, 0.6 * inch, width - 1 * inch, 0.6 * inch)  # Footer separator
            c.setStrokeColorRGB(0, 0, 0)
            c.showPage()
            page_num += 1
            c.setFont("Times-Bold", 18)
            c.drawString(1 * inch, height - 0.4 * inch, "Anomaly Images (Continued)")
            c.setLineWidth(0.5)
            c.setStrokeColorRGB(0.5, 0.5, 0.5)
            c.line(1 * inch, height - 0.5 * inch, width - 1 * inch, height - 0.5 * inch)  # Underline
            c.setStrokeColorRGB(0, 0, 0)
            y_pos = height - 1.2 * inch
            images_per_page = 0
        
        # Draw the anomaly image
        c.setFont("Times-Bold", 12)
        c.drawString(1.1 * inch, y_pos - 0.2 * inch, f"Anomaly {i+1}: {anomaly['type']}, Max Temp: {anomaly['max_temp']:.1f}°C")
        y_pos -= 0.5 * inch
        
        anomaly_img = anomaly['image']
        if anomaly_img is None:
            continue
        
        temp_anomaly_path = os.path.join(os.path.dirname(output_path), f"temp_anomaly_{i+1}.jpg")
        if not cv2.imwrite(temp_anomaly_path, anomaly_img):
            logger.error(f"Failed to save anomaly image at {temp_anomaly_path}")
            continue
        
        c.drawImage(temp_anomaly_path, 1 * inch, y_pos - 2.0 * inch, 2.5 * inch, 2.0 * inch)  # Larger image
        y_pos -= 2.2 * inch
        
        # Draw Maintenance Action
        maintenance_action = {
            'Severe Hot Spot': "Inspect and replace faulty module or wiring immediately.",
            'Hot Spot': "Clean panel surface, check for shading or defects, schedule repair.",
            'Warm Spot': "Monitor panel performance, schedule cleaning if needed.",
            'Minor Anomaly': "Log for future monitoring, no immediate action required."
        }.get(anomaly['type'], "Monitor and reassess during next inspection.")
        c.setFont("Times-Bold", 10)
        c.drawString(1.1 * inch, y_pos - 0.2 * inch, "Maintenance Action:")
        y_pos -= 0.3 * inch  # Move down for the text
        c.setFont("Times-Roman", 9)
        text_lines = []
        current_line = ""
        for word in maintenance_action.split():
            if len(current_line + word) < 80:  # Approximate character limit per line
                current_line += word + " "
            else:
                text_lines.append(current_line.strip())
                current_line = word + " "
        if current_line:
            text_lines.append(current_line.strip())
        
        for line in text_lines:
            c.drawString(1.2 * inch, y_pos - 0.2 * inch, line)
            y_pos -= 0.3 * inch
        
        # Calculate the height of the Maintenance Action text block and adjust y_pos
        maintenance_lines = len(text_lines)
        maintenance_height = maintenance_lines * 0.3 * inch  # 0.3 inches per line
        y_pos -= 0.1 * inch  # Additional spacing after Maintenance Action
        
        # Draw Annotation
        c.setFont("Times-Bold", 10)
        c.drawString(1.1 * inch, y_pos - 0.2 * inch, "Annotation:")
        y_pos -= 0.3 * inch  # Move down for the text
        c.setFont("Times-Roman", 9)
        text_lines = []
        current_line = ""
        for word in anomaly['annotation'].split():
            if len(current_line + word) < 80:
                current_line += word + " "
            else:
                text_lines.append(current_line.strip())
                current_line = word + " "
        if current_line:
            text_lines.append(current_line.strip())
        
        for line in text_lines:
            c.drawString(1.2 * inch, y_pos - 0.2 * inch, line)
            y_pos -= 0.3 * inch
        y_pos -= 0.5 * inch  # Extra spacing between entries
        
        # Clean up temporary file
        if os.path.exists(temp_anomaly_path):
            os.remove(temp_anomaly_path)
        
        images_per_page += 1
    
    # Finalize the last page of anomaly images
    c.setFont("Times-Roman", 8)
    c.drawString(1 * inch, 0.5 * inch, f"Thermal Analysis | Contact: MRDrones@mastec.com | Page {page_num}")
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0.5, 0.5, 0.5)
    c.line(1 * inch, 0.6 * inch, width - 1 * inch, 0.6 * inch)  # Footer separator
    c.setStrokeColorRGB(0, 0, 0)
    c.showPage()
    page_num += 1
    
    # Page: Recommendations
    c.setFont("Times-Bold", 18)
    c.drawString(1 * inch, height - 0.4 * inch, "Recommendations")
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0.5, 0.5, 0.5)
    c.line(1 * inch, height - 0.5 * inch, width - 1 * inch, height - 0.5 * inch)  # Underline
    c.setStrokeColorRGB(0, 0, 0)
    
    c.setFont("Times-Bold", 12)
    c.drawString(1.1 * inch, height - 1.1 * inch, "Action Plan")
    c.setFont("Times-Roman", 9)
    y_pos = height - 1.5 * inch
    critical_count = sum(1 for anomaly in anomalies if anomaly['severity'] == 'Critical')
    if critical_count > 0:
        c.drawString(1.2 * inch, y_pos, f"- {critical_count} critical anomalies detected. Immediate inspection and repair required.")
        y_pos -= 0.3 * inch
    
    moderate_count = sum(1 for anomaly in anomalies if anomaly['severity'] == 'Moderate')
    if moderate_count > 0:
        c.drawString(1.2 * inch, y_pos, f"- {moderate_count} moderate anomalies detected. Schedule maintenance within the next month.")
        y_pos -= 0.3 * inch
    
    c.drawString(1.2 * inch, y_pos, "- Review KML file for anomaly locations in Google Earth.")
    y_pos -= 0.3 * inch
    c.drawString(1.2 * inch, y_pos, "- Regular thermal inspections recommended every 6 months.")
    y_pos -= 0.3 * inch
    c.drawString(1.2 * inch, y_pos, "- Compare with historical data to identify recurring issues.")
    
    # Technician Notes Section
    c.setFont("Times-Bold", 12)
    c.drawString(1.1 * inch, y_pos - 0.4 * inch, "Technician Notes")
    y_pos -= 0.7 * inch
    c.setFont("Times-Roman", 9)
    c.drawString(1.2 * inch, y_pos, "Notes: ____________________________________________________________")
    y_pos -= 0.3 * inch
    c.drawString(1.2 * inch, y_pos, "____________________________________________________________")
    y_pos -= 0.3 * inch
    c.drawString(1.2 * inch, y_pos, "Actions Taken: ______________________________________________________")
    
    # Footer
    c.setFont("Times-Roman", 8)
    c.drawString(1 * inch, 0.5 * inch, f"Thermal Analysis | Contact: MRDrones@mastec.com | Page {page_num}")
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0.5, 0.5, 0.5)
    c.line(1 * inch, 0.6 * inch, width - 1 * inch, 0.6 * inch)  # Footer separator
    c.setStrokeColorRGB(0, 0, 0)
    c.showPage()
    page_num += 1
    
    # Page: Additional Deliverables
    c.setFont("Times-Bold", 18)
    c.drawString(1 * inch, height - 0.4 * inch, "Additional Deliverables")
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0.5, 0.5, 0.5)
    c.line(1 * inch, height - 0.5 * inch, width - 1 * inch, height - 0.5 * inch)  # Underline
    c.setStrokeColorRGB(0, 0, 0)
    
    c.setFont("Times-Bold", 12)
    c.drawString(1.1 * inch, height - 1.1 * inch, "Resources")
    kml_path_output = os.path.join(os.path.dirname(output_path), "Thermal_Analysis_GeoTIFF_Anomalies.kml")
    generate_kml(anomalies, kml_path_output, kml_path, tfw_path)
    c.setFont("Times-Roman", 9)
    c.drawString(1.2 * inch, height - 1.5 * inch, f"KML File: {os.path.basename(kml_path_output)}")
    c.drawString(1.2 * inch, height - 1.8 * inch, "Use this KML file to view anomaly locations in Google Earth.")
    c.drawString(1.2 * inch, height - 2.1 * inch, "Note: Coordinates are in WGS84 (latitude, longitude).")
    
    # Footer
    c.setFont("Times-Roman", 8)
    c.drawString(1 * inch, 0.5 * inch, f"Thermal Analysis | Contact: MRDrones@mastec.com | Page {page_num}")
    c.setLineWidth(0.5)
    c.setStrokeColorRGB(0.5, 0.5, 0.5)
    c.line(1 * inch, 0.6 * inch, width - 1 * inch, 0.6 * inch)  # Footer separator
    c.setStrokeColorRGB(0, 0, 0)
    
    c.save()
    if os.path.exists(temp_processed_path):
        os.remove(temp_processed_path)
        logger.info(f"Removed temporary file: {temp_processed_path}")
    if 'temp_hist_path' in locals() and os.path.exists(temp_hist_path):
        os.remove(temp_hist_path)
        logger.info(f"Removed temporary file: {temp_hist_path}")
    if 'pie_path' in locals() and os.path.exists(pie_path):
        os.remove(pie_path)
        logger.info(f"Removed temporary file: {pie_path}")
    if 'bar_path' in locals() and os.path.exists(bar_path):
        os.remove(bar_path)
        logger.info(f"Removed temporary file: {bar_path}")
    logger.info(f"GeoTIFF PDF report generated: {output_path}")

def generate_geotiff_csv_report(output_path, result):
    """Generate a CSV report for a single GeoTIFF with optional KML and TFW."""
    logger.info(f"Generating GeoTIFF CSV report: {output_path}")
    data = []
    image_path = result['image_path']
    for i, anomaly in enumerate(result['anomalies']):
        priority = 1 if anomaly['severity'] == 'Critical' else (2 if anomaly['severity'] == 'Moderate' else 3)
        maintenance_action = {
            'Severe Hot Spot': "Inspect and replace faulty module or wiring immediately.",
            'Hot Spot': "Clean panel surface, check for shading or defects, schedule repair.",
            'Warm Spot': "Monitor panel performance, schedule cleaning if needed.",
            'Minor Anomaly': "Log for future monitoring, no immediate action required."
        }.get(anomaly['type'], "Monitor and reassess during next inspection.")
        anomaly_data = {
            'Image': os.path.basename(image_path),
            'Anomaly_ID': i + 1,
            'Priority': priority,
            'Center_X': anomaly['center_x'],
            'Center_Y': anomaly['center_y'],
            'Display_X': anomaly['display_x'],
            'Display_Y': anomaly['display_y'],
            'Area': anomaly['area'],
            'Max_Temperature': anomaly['max_temp'],
            'Type': anomaly['type'],
            'Severity': anomaly['severity'],
            'Annotation': anomaly['annotation'],
            'Coord_X': anomaly.get('coord_x', 'N/A'),
            'Coord_Y': anomaly.get('coord_y', 'N/A'),
            'Latitude': anomaly.get('latitude', 'N/A'),
            'Longitude': anomaly.get('longitude', 'N/A'),
            'Temp_Delta': anomaly.get('temp_delta', 'N/A'),
            'Area_m2': anomaly.get('area_m2', 'N/A'),
            'Maintenance_Action': maintenance_action
        }
        data.append(anomaly_data)
    
    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False)
    logger.info(f"GeoTIFF CSV report generated: {output_path}")