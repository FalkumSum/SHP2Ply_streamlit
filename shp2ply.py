import io
import zipfile
import tempfile
from pathlib import Path

import geopandas as gpd
import streamlit as st


def geodf_to_ply_string(gdf):
    """
    Convert a GeoDataFrame of Polygon / MultiPolygon geometries
    to a Geosoft-style PLY string.
    """
    buf = io.StringIO()
    poly_counter = 1

    for geom in gdf.geometry:
        if geom is None:
            continue

        # Handle MultiPolygon vs Polygon
        if geom.geom_type == "MultiPolygon":
            polygons = list(geom.geoms)
        elif geom.geom_type == "Polygon":
            polygons = [geom]
        else:
            # Ignore non-polygon geometry types
            continue

        for poly in polygons:
            buf.write(f"poly {poly_counter}\n")

            x, y = poly.exterior.xy
            for xi, yi in zip(x, y):
                buf.write(f"   {xi:.2f}   {yi:.2f} \n")

            buf.write("\n")  # blank line after each polygon
            poly_counter += 1

    return buf.getvalue()


def print_gdf_details_to_streamlit(gdf):
    """
    Show CRS, EPSG, geometry types, bounds, etc. in Streamlit.
    """
    st.subheader("GeoDataFrame details")

    st.write("**Raw CRS:**", gdf.crs)

    epsg = None
    if gdf.crs is not None:
        try:
            epsg = gdf.crs.to_epsg()
        except Exception:
            epsg = None

    st.write("**Detected EPSG:**", epsg if epsg is not None else "Unable to determine")

    if gdf.crs is not None:
        st.write("**CRS WKT snippet:**")
        st.text(gdf.crs.to_wkt()[:400] + "...")
    else:
        st.write("**CRS WKT snippet:** None (no CRS assigned)")

    st.write("**Columns:**", list(gdf.columns))

    st.write("**Geometry type counts:**")
    st.write(gdf.geometry.geom_type.value_counts())

    st.write("**Total features:**", len(gdf))

    st.write("**Bounds [minx, miny, maxx, maxy]:**")
    st.write(gdf.total_bounds)

    st.write("**Head():**")
    st.write(gdf.head())


def load_shapefile_from_zip(uploaded_zip) -> gpd.GeoDataFrame:
    """
    Take an uploaded zip (Streamlit UploadedFile) containing a shapefile,
    extract to a temporary directory, and load with GeoPandas.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Save uploaded zip to temp
        zip_path = tmpdir_path / "upload.zip"
        with open(zip_path, "wb") as f:
            f.write(uploaded_zip.read())

        # Extract all files
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmpdir_path)

        # Find a .shp file
        shp_files = list(tmpdir_path.rglob("*.shp"))
        if not shp_files:
            raise FileNotFoundError("No .shp file found inside the ZIP.")

        shp_path = shp_files[0]  # use the first one
        gdf = gpd.read_file(shp_path)

        return gdf


def main():
    st.title("SHP → Geosoft PLY Converter")

    st.markdown(
        """
    Upload a **zipped shapefile** (`.zip` containing `.shp`, `.shx`, `.dbf`, `.prj`, etc.),
    choose an output EPSG, and download a **Geosoft .ply** polygon file.
    
    The output format is like:
    
    ```text
    poly 1
       301437.63   5900640.93 
       299896.20   5900350.59 
        """
    )
    
    uploaded_zip = st.file_uploader(
        "Upload zipped shapefile (.zip)",
        type=["zip"],
    )
    
    if uploaded_zip is None:
        st.info("Please upload a .zip file containing your shapefile.")
        return
    
    # Load shapefile
    try:
        gdf = load_shapefile_from_zip(uploaded_zip)
    except Exception as e:
        st.error(f"Failed to read shapefile from ZIP: {e}")
        return
    
    # Filter to polys only
    gdf = gdf[gdf.geometry.notnull()]
    gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
    
    if gdf.empty:
        st.error("No Polygon or MultiPolygon geometries found in the shapefile.")
        return
    
    # Show details
    print_gdf_details_to_streamlit(gdf)
    
    # Detect EPSG for default
    epsg_detected = None
    if gdf.crs is not None:
        try:
            epsg_detected = gdf.crs.to_epsg()
        except Exception:
            epsg_detected = None
    
    default_epsg = epsg_detected if epsg_detected is not None else 4326
    
    st.subheader("Output settings")
    
    output_epsg = st.number_input(
        "Output EPSG",
        value=int(default_epsg),
        step=1,
        help="The shapefile will be reprojected to this EPSG before writing the PLY.",
    )
    
    output_filename = st.text_input(
        "Output PLY file name",
        value="output.ply",
    )
    
    if st.button("Convert to PLY"):
        # Reproject
        try:
            gdf_out = gdf.to_crs(epsg=int(output_epsg))
        except Exception as e:
            st.error(f"Error reprojecting to EPSG:{output_epsg} → {e}")
            return
    
        # Convert to PLY text
        ply_text = geodf_to_ply_string(gdf_out)
    
        st.success("PLY conversion successful!")
    
        # Preview first lines
        st.subheader("PLY preview (first 50 lines)")
        preview_lines = "\n".join(ply_text.splitlines()[:50])
        st.code(preview_lines, language="text")
    
        # Download button
        st.download_button(
            label="Download PLY file",
            data=ply_text.encode("utf-8"),
            file_name=output_filename or "output.ply",
            mime="text/plain",
        )
