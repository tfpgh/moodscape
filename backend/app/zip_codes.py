import pandas as pd

zip_code_df = pd.read_csv(
    "app/US_zip_code_data.txt",
    delimiter="\t",
    header=None,
    names=[
        "Country Code",
        "Zip Code",
        "Place Name",
        "State Name",
        "State Code",
        "Admin Name 2",
        "Admin Code 2",
        "Admin Name 3",
        "Admin Code 3",
        "Latitude",
        "Longitude",
        "Accuracy",
    ],
)

STATE_LIST = sorted(
    filter(lambda state: isinstance(state, str), zip_code_df["State Name"].unique())
)

ZIP_CODE_MAPPING: dict[str, str] = {
    str(code): state
    for code, state in zip(
        zip_code_df["Zip Code"], zip_code_df["State Name"], strict=True
    )
    if isinstance(state, str)
}
