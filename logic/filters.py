def is_valid_product(adapter_data, supplier_name='FARNELL'):
    """
    מסנן מוצרים לפי חוקים עסקיים, מותאם לספק ספציפי.
    """
    if not adapter_data:
        return False, "No Data / Product Not Found"

    # ==========================
    # חוקים עבור FARNELL
    # ==========================
    if supplier_name == 'FARNELL':
        # בדיקה 1: תקינות בסיסית
        if not adapter_data.get('1_Product_Name'):
            return False, "Missing Product Name"

        try:
            cost = float(adapter_data.get('5_Cost_Buy', 0))
            if cost <= 0:
                return False, "Zero Cost (Likely Obsolete)"
        except:
            return False, "Invalid Cost Format"

        # חילוץ נתונים
        status = str(adapter_data.get('_status', 'UNKNOWN')).upper()
        stock = int(adapter_data.get('Extra_Stock', 0))
        warehouse = str(adapter_data.get('_warehouse', 'UK')).upper()
        is_direct_ship = adapter_data.get('_is_direct_ship', False)

        # בדיקה 2: חוק העל - מחסן ארה"ב הוא תמיד תקין
        if warehouse == 'USA' or warehouse == 'US':
            return True, "OK"

        # בדיקה 3: Direct Ship (שהוא לא ארה"ב)
        if status == 'DIRECT_SHIP' or is_direct_ship is True:
            return False, "Direct Ship (Non-USA) - Cannot Import"

        # בדיקה 4: סטטוסים בעייתיים
        bad_statuses = ['NO_LONGER_STOCKED', 'NO_LONGER_MANUFACTURED', 'NLS', 'NLM', 'OBSOLETE']
        
        if status in bad_statuses:
            if stock == 0:
                return False, f"Status {status} & Zero Stock"

        return True, "OK"

    # ==========================
    # חוקים עבור ספקים אחרים (בעתיד)
    # ==========================
    # elif supplier_name == 'DIGIKEY':
    #     pass

    return True, "OK (Default)"