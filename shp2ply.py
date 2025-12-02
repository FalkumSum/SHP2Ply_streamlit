import io
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
        except:
            epsg = None
    st.write("Detected EPSG:", epsg if epsg else "Unknown")

    st.write("Columns:", list(gdf.columns))
    st.write("Geometry types:", gdf.geometry.geom_type.value_counts())
    st.write("Total features:", len(gdf))
    st.write("Bounds:", gdf.total_bounds)
    st.write("Head():")
    st.write(gdf.head())


def load_shapefile_from_batch(files):
    """
    Accept multiple uploaded files, save them into a temporary
    directory, and load the shapefile.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        for f in files:
            file_path = tmpdir / f.name
            with open(file_path, "wb") as out:
                out.write(f.read())

        shp_files = list(tmpdir.rglob("*.shp"))
        if not shp_files:
            raise FileNotFoundError("No .shp found. Select all required shapefile components.")

        return gpd.read_file(shp_files[0])


def main():
    st.title("SHP → Geosoft PLY Converter (Batch Upload Mode)")

    st.write("Upload **all shapefile components** (.shp, .shx, .dbf, .prj, etc.) at once.")

    uploaded_files = st.file_uploader(
        "Upload shapefile components",
        type=["shp", "shx", "dbf", "prj", "cpg"],
        accept_multiple_files=True
    )

    if not uploaded_files:
        st.info("Select all shapefile files to continue.")
        return

    try:
        gdf = load_shapefile_from_batch(uploaded_files)
    except Exception as e:
        st.error(f"Failed to load shapefile: {e}")
        return

    gdf = gdf[gdf.geometry.notnull()]
    gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]

    if gdf.empty:
        st.error("No polygon geometries found.")
        return

    print_gdf_details_to_streamlit(gdf)

    epsg = None
    if gdf.crs:
        try:
            epsg = gdf.crs.to_epsg()
        except:
            epsg = None

    default_epsg = epsg if epsg else 4326

    st.subheader("Output settings")
    output_epsg = st.number_input("Output EPSG", value=int(default_epsg), step=1)
    output_filename = st.text_input("Output PLY filename", value="output.ply")

    if st.button("Convert to PLY"):
        try:
            gdf_out = gdf.to_crs(epsg=int(output_epsg))
        except Exception as e:
            st.error(f"CRS reprojection error: {e}")
            return

        ply_text = geodf_to_ply_string(gdf_out)

        st.success("Conversion successful!")
        st.code("\n".join(ply_text.splitlines()[:50]), language="text")

        st.download_button(
            "Download PLY",
            data=ply_text.encode("utf-8"),
            file_name=output_filename,
            mime="text/plain"
        )


if __name__ == "__main__":
    main()
