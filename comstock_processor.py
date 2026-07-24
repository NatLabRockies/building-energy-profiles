"""
ComStock Processor - A tool to download and process ComStock data.

This package provides utilities for downloading metadata and time series data
from NREL's ComStock dataset hosted on AWS S3.

@author: nllong
"""

import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm


class ComStockProcessor:
    def __init__(self, state: str, county_name: str, building_type: str, upgrade: str, base_dir: Path) -> None:
        """ComStockProcess class helps users download metadata and time series data from the ComStock dataset.

        Args:
            state (str): 2-letter state abbreviation
            county_name (str): name of the county
            building_type (str): type of building
            upgrade (str): upgrade identifier from ComStock, e.g., 0 = baseline
            base_dir (Path): directory to save the downloaded ComStock files
        """
        self.state = state
        self.county_name = county_name
        self.building_type = building_type
        self.upgrade = upgrade
        self.base_dir = base_dir

        if not self.base_dir.exists():
            self.base_dir.mkdir()

        # Data lake explorer link: https://data.openei.org/s3_viewer?bucket=oedi-data-lake&prefix=nrel-pds-building-stock%2Fend-use-load-profiles-for-us-building-stock%2F2024%2Fcomstock_amy2018_release_1%2F

        self.base_url = "https://oedi-data-lake.s3.amazonaws.com/nrel-pds-building-stock/end-use-load-profiles-for-us-building-stock/2024/comstock_amy2018_release_1/"
        # TODO: need to update the location of the metadata for comstock_amy2018_release_2, so leaving it ias release_1 for now.

        self.metadata_url = self.base_url + "metadata"
        self.time_series_url = self.base_url + "timeseries_individual_buildings"

    def download_file(self, url: str, save_path: Path) -> None:
        response = requests.get(url, timeout=300)
        if response.status_code == 200:
            with open(save_path, "wb") as file:
                file.write(response.content)
            # TODO: need to create valid logger so that we don't always show these messages
            # tqdm.write(f"File downloaded successfully: {save_path}")
        else:
            tqdm.write(f"Failed to download file: {url}")

    def process_metadata(self, save_dir: Path) -> pd.DataFrame:
        """Download (if needed) and process the comstock metadata. This process will only download if it is not already persisted.
        The method can take a few minutes since the datafile can be heavy.

        Args:
            save_dir (Path): path to save the metadata

        Returns:
            DataFrame: the resulting metadata filtered by the classes "constraints".
        """
        # check if the parquet already exists, don't download it again if so, but give a warning
        if (save_dir / "comstock_metadata.parquet").exists():
            print("Metadata parquet already exists. Skipping download.")
        else:
            download_file = f"{self.metadata_url}/baseline.parquet"
            print(f"Downloading metadata file: {download_file}")
            self.download_file(download_file, save_path=save_dir / "comstock_metadata.parquet")

        # check if the csv already exists, don't create it again if so, but give a warning
        output_csv = save_dir / f"{self.state}-{self.county_name}-{self.building_type}-{self.upgrade}-selected_metadata.csv"
        if output_csv.exists():
            print(f"Metadata csv already exists. Skipping creation. Delete {output_csv} if you want to save again.")
            meta_df = pd.read_csv(output_csv)

            return meta_df

        # filter
        filters = []
        if self.state != "All":
            filters.append(("in.state", "==", self.state))

        if self.county_name != "All":
            if self.state == "All":
                print("County is specified, but State is not. Ignoring County...")
            else:
                filters.append(("in.county_name", "==", f"{self.state}, {self.county_name}"))

        if self.building_type != "All":
            filters.append(("in.comstock_building_type", "==", self.building_type))

        # read
        meta_df = pd.read_parquet(save_dir / "comstock_metadata.parquet", filters=None if len(filters) == 0 else filters)
        meta_df = meta_df.reset_index(drop=False)

        # save to csv
        meta_df.to_csv(output_csv, index=False)

        return meta_df

    def process_building_time_series(self, data_frame: pd.DataFrame, save_dir: Path) -> tuple[list[Path], list[str]]:
        """Pull the latest time series data from the BuildStock data files online using parallel execution."""
        num_workers = max(1, multiprocessing.cpu_count() - 1)
        print(f"Number of workers: {num_workers}")

        def download_task(row: pd.Series) -> tuple[Path, str]:
            building_id = str(row["bldg_id"])

            # Check if file already exists
            save_path = save_dir / f"bldg_id-{building_id}-upgrade-{self.upgrade}.parquet"
            if save_path.exists():
                return save_path, building_id

            building_time_series_file = (
                f"{self.time_series_url}/by_state/upgrade={self.upgrade}/state={row['in.state']}/{building_id}-{self.upgrade}.parquet"
            )
            self.download_file(building_time_series_file, save_path)
            return save_path, building_id

        data_rows = [row for _, row in data_frame.iterrows()]
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            results = list(tqdm(executor.map(download_task, data_rows), total=len(data_rows)))

        # break out the paths and building_ids
        paths, building_ids = zip(*results) if results else ([], [])
        return list(paths), list(building_ids)


def main() -> None:
    # Settings for modification
    state = "CA"
    county_name = "All"
    building_type = "All"
    upgrade = "0"

    base_dir = Path().resolve() / "datasets" / "comstock"
    timeseries_save_dir = base_dir / "timeseries"
    for d in [base_dir, timeseries_save_dir]:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)

    processor = ComStockProcessor(state, county_name, building_type, upgrade, base_dir)
    meta_df = processor.process_metadata(save_dir=base_dir)

    processor.process_building_time_series(meta_df, save_dir=timeseries_save_dir)


if __name__ == "__main__":
    main()
