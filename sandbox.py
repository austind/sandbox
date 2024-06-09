def wildcard_to_cidr(wildcard_mask):
    # Convert the wildcard mask to an integer
    wildcard_mask_int = sum(
        [int(bit) * (2 ** (7 - i)) for i, bit in enumerate(wildcard_mask.split("."))]
    )

    # Invert the bits of the wildcard mask
    inverted_mask_int = wildcard_mask_int ^ 0xFF

    # Calculate the number of bits that are set to 0 in the inverted wildcard mask
    cidr_prefix = bin(inverted_mask_int).count("0")

    return cidr_prefix


if __name__ == "__main__":
    print(wildcard_to_cidr("0.0.0.255"))
