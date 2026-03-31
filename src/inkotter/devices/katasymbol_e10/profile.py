"""Katasymbol E10 profile facts.

This profile intentionally encodes verified V1 facts as stable input for V2.
"""

from inkotter.devices.base import (
    BluetoothDiscoveryHints,
    DeviceProfile,
    ProtocolProfile,
    RasterProfile,
)


KATASYMBOL_E10_PRELUDE = (
    ("aa11", bytes.fromhex("0100000100000000")),
    ("aa30", bytes.fromhex("0100000100000000")),
    ("aa18", bytes.fromhex("0100000100000000")),
    ("aa11", bytes.fromhex("0100000100000000")),
    ("aa30", bytes.fromhex("0100000100000000")),
    ("aa18", bytes.fromhex("0100000100000000")),
    ("aa11", bytes.fromhex("0100000100000000")),
    ("aa11", bytes.fromhex("0100000100000000")),
    ("aad0", bytes.fromhex("360000010200000200002c020300000000")),
    ("aad1", bytes.fromhex("edef00025d0020000000200000000000000050807e2f02e44880df15dce88c745ae280985f31df88da9bcc2112814f5afa374d0c6dfce5fd5716ec195a8a28325d674fb6e4c7dc5d2fdc6896fb28c72b010e59b55381f208f9bd6a26ecdcdc0cf06a5cbd32e05222fc07545fdf081a48c9a0dcf0ea27af3db0fe07070a96dba291cb4858e753d6b642fa4c7167b3fc2cf0365534d5c02c079e409e537bb42be118e60ce455dbc7da2b47b32ef60ecbdc040b1e0c7df73549eb3490e8d56f1403bc3ecf9b415189eaf974e585b89caf3644bd592217d79e5fbfe225977aa02f780164547aa1389e8c0ae928bb9117570a13bdc3aae06b8ac4067953f78476127e69fbfc00cf15a777620cb8fd5182349c5d24fd2335f3007712d47d15965309f535a683b82f9433b01d7f5c22900e237a5c66a186a09cbe698ee2aaea76a40fd4f542b5511e16c5fafd42252d8bdbd30c95baab64d5f04280d22afc7b4407177df5513df0a3e535b2bf95a5a44d19e496ed9a96194b38cfee574e415e7c8f7361adb8bd26cd3718cb10b2eef05d7e0ddedf270489142d73532f4181f3e1314d131ffe75e5fe544a06f6f4e41f12748557b6a4aa50928702ee1f39a62314f216fa11e716a5f7db06309923654bb4a180e2e5dbe1377aa28b99b720b5c58c50c3293f69cb4e012f4242daa99fd7662a358025880a46efd7a4b6")),
    ("aad1", bytes.fromhex("091f01029e16688663aecc9aedbdc96b607ec554d33aed665d20410a67e05590599bc43e2ec06a817377b1a8b144ec4312fa1d999d027061e81de7000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000a46efd7a4b6")),
    ("aa11", bytes.fromhex("0100000100000000")),
    ("aab0", bytes.fromhex("920100013230323630333232000000000000")),
    ("aa11", bytes.fromhex("0100000100000000")),
    ("aa11", bytes.fromhex("0100000100000000")),
    ("aa30", bytes.fromhex("0100000100000000")),
    ("aa18", bytes.fromhex("0100000100000000")),
    ("aa11", bytes.fromhex("0100000100000000")),
    ("aa11", bytes.fromhex("0100000100000000")),
    ("aa30", bytes.fromhex("0100000100000000")),
    ("aa18", bytes.fromhex("0100000100000000")),
    ("aa11", bytes.fromhex("0100000100000000")),
    ("aa11", bytes.fromhex("0100000100000000")),
    ("aa30", bytes.fromhex("0100000100000000")),
    ("aa18", bytes.fromhex("0100000100000000")),
    ("aa11", bytes.fromhex("0100000100000000")),
    ("aa11", bytes.fromhex("0100000100000000")),
    ("aa11", bytes.fromhex("0100000100000000")),
    ("aa11", bytes.fromhex("0100000100000000")),
    ("aac9", bytes.fromhex("6f0000016e000000")),
    ("aa13", bytes.fromhex("0100000100000000")),
    ("aa11", bytes.fromhex("0100000100000000")),
    ("aaba", bytes.fromhex("1a00000119000000")),
    ("aa11", bytes.fromhex("0100000100000000")),
)

KATASYMBOL_E10_PROFILE = DeviceProfile(
    key="katasymbol_e10",
    display_name="Katasymbol E10",
    marketing_name="Katasymbol E10",
    discovery=BluetoothDiscoveryHints(
        name_patterns=("katasymbol", "t0"),
        rfcomm_channels=(1, 2, 3),
        needs_root_hint=True,
    ),
    raster=RasterProfile(
        pixels_per_mm=8.0,
        head_height_px=96,
        bytes_per_column=12,
        btbuf_data_offset=14,
        page_width_px=332,
        trim_probe_columns=48,
        first_page_left_margin=1,
        later_page_left_margin=1,
        right_margin=1,
        multi_page_supported=True,
        fitted_content_height_px=88,
        actual_size_single_page_max_width_mm=39.0,
    ),
    protocol=ProtocolProfile(
        transport_family="t15",
        image_payload_cmd="aabb",
        page_start_cmd="aa5c",
        print_trigger_cmd="aa10",
        print_trigger_payload=bytes.fromhex("0100000100000000"),
        start_transfer_payload_length=512,
        single_page_flags=0x100E,
        continue_page_flags=0x1002,
        final_page_flags=0x100C,
        compression="lzma-alone",
        prelude_packets=KATASYMBOL_E10_PRELUDE,
    ),
    notes=(
        "Verified on Katasymbol E10 hardware and matching manufacturer captures.",
        "Wide labels use multiple AA BB pages rather than a separate image transport family.",
        "The practical everyday path uses the vendor-nearer T15 raster family.",
    ),
)
