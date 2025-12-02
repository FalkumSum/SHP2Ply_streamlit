import io
import zipfile
import tempfile
from pathlib import Path

import geopandas as gpd
import streamlit as st


def geodf_to_ply_string(gdf):
    buf = io.StringIO()
    poly_counter = 1

    for geom in gdf.geometry:
        if geom is None:
            continue

        if geom.geom_type == "MultiPolygon":
            polygons = list(geom.geoms)
        elif geom.geom_type == "Polygon":
            polygons = [geom]
        else:
            continue

        for poly in polygons:
            buf.write("poly {}\n".format(poly_counter))
            x, y = poly.exterior.xy
            for xi, yi in zip(x, y):
                buf.write("   {:.2f}   {:.2f} \n".format(xi, yi))
            buf.write("\n")
            poly_counter += 1

    return buf.getvalue()


def print_gdf_details_to_streamlit(gdf):
    st.subheader("GeoDataFrame details")

    st.write("Raw CRS:", gdf.crs)

    epsg = None
    if gdf.crs is not None:
        try:
            epsg = gdf.crs.to_epsg()
        except Exception:
            epsg = None

    st.write("Detected EPSG:", epsg if epsg is not None else "Unable to determine")

    if gdf.crs is not None:
        st.write("CRS WKT snippet:")
        st.text(gdf.crs.to_wkt()[:400] + "...")
    else:
        st.write("CRS WKT snippet: None (no CRS assigned)")

    st.write("Columns:", list(gdf.columns))
    st.write("Geometry type counts:", gdf.geometry.geom_type.value_counts())
    st.write("Total features:", len(gdf))
    st.write("Bounds [minx, miny, maxx, maxy]:", gdf.total_bounds)
    st.write("Head():")
    st.write(gdf.head())


def load_shapefile_from_zip(uploaded_zip):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        zip_path = tmpdir_path / "upload.zip"

        with open(zip_path, "wb") as f:
            f.write(uploaded_zip.read())

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmpdir_path)

        shp_files = list(tmpdir_path.rglob("*.shp"))
        if not shp_files:
            raise FileNotFoundError("No .shp file found inside ZIP.")

        return gpd.read_file(shp_files[0])


def load_shapefile_from_path(shp_path):
    return gpd.read_file(shp_path)


def main():
    st.title("SHP → Geosoft PLY Converter")

    st.write(
        "Upload a zipped shapefile (.shp + .shx + .dbf + .prj) OR provide a local .shp path. "
        "Then choose output EPSG and download the .ply file."
    )

    mode = st.radio("Input source", ["Upload ZIP", "Local SHP path"])

    gdf = None

    if mode == "Upload ZIP":
        uploaded_zip = st.file_uploader("Upload ZIP file", type=["zip"])
        if uploaded_zip is None:
            st.info("Please upload a .zip shapefile.")
            return

        try:
            gdf = load_shapefile_from_zip(uploaded_zip)
        except Exception as e:
            st.error("Failed to read shapefile: {}".format(e))
            return

    else:
        shp_path = st.text_input(
            "Full path to .shp file",
            value=r"C:\SkyTEM\Software\example\polygon.shp"
        )

        if not shp_path.strip():
            st.info("Please enter a valid path.")
            return

        try:
            gdf = load_shapefile_from_path(shp_path)
        except Exception as e:
            st.error("Failed to read shapefile: {}\nPath: {}".format(e, shp_path))
            return

    gdf = gdf[gdf.geometry.notnull()]
    gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]

    if gdf.empty:
        st.error("No Polygon or MultiPolygon geometries found.")
        return

    print_gdf_details_to_streamlit(gdf)

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
        step=1
    )

    output_filename = st.text_input("Output PLY filename", value="output.ply")

    if st.button("Convert to PLY"):
        try:
            gdf_out = gdf.to_crs(epsg=int(output_epsg))
        except Exception as e:
            st.error("Error reprojecting: {}".format(e))
            return

        ply_text = geodf_to_ply_string(gdf_out)

        st.success("PLY conversion successful!")

        st.subheader("First 50 lines of PLY output")
        preview = "\n".join(ply_text.splitlines()[:50])
        st.code(preview)

        st.download_button(
            "Download PLY file",
            data=ply_text.encode("utf-8"),
            file_name=output_filename,
            mime="text/plain"
        )


if __name__ == "__main__":
    main()
