;;; import_attrs.lsp
;;; MVP-0.6: Import CSV attribute values into DWG block references by GUID.
;;; Command: IMPORT_ATTRS
;;; Constraints: AutoLISP only; update existing attributes only; never modify GUID.

(defun c:IMPORT_ATTRS (/ basepath dict-panel dict-circuits dict-sections
                        ss i n ent edata blocks-scanned blocks-with-guid
                        updated-count skipped-no-guid guid-not-found
                        guid mode attrs-to-apply)
  (princ "\nIMPORT_ATTRS: Import CSV attributes into blocks by GUID.")
  ;; 1) Prompt for folder containing CSV files
  (setq basepath (getstring T "\nEnter folder path containing CSV files (e.g. out/ or C:/out): "))
  (if (or (not basepath) (= (strlen (vl-string-trim " \t" basepath)) 0))
    (progn (princ "\nCancelled.") (princ))
    (progn
      (setq basepath (vl-string-trim " \t" basepath))
      ;; Ensure trailing separator for path concatenation
      (if (and (> (strlen basepath) 0)
               (not (wcmatch basepath "*[/\\]")))
        (setq basepath (strcat basepath "/")))
      ;; 2) Load and parse 3 CSV files
      (setq dict-panel   (_import_parse_csv_2col (strcat basepath "attrs_panel.csv")))
      (setq dict-circuits (_import_parse_csv_2col (strcat basepath "attrs_circuits.csv")))
      (setq dict-sections (_import_parse_csv_3col (strcat basepath "attrs_sections.csv")))
      ;; 3) Initialize counters
      (setq blocks-scanned 0
            blocks-with-guid 0
            updated-count 0
            skipped-no-guid 0
            guid-not-found 0)
      ;; 4) Get all INSERT entities in drawing
      (setq ss (ssget "X" '((0 . "INSERT"))))
      (if ss
        (progn
          (setq n (sslength ss))
          (setq i 0)
          (repeat n
            (setq ent (ssname ss i))
            (setq blocks-scanned (1+ blocks-scanned))
            (setq edata (entget ent))
            ;; Check if block has attributes (DXF 66 = 1)
            (if (= (cdr (assoc 66 edata)) 1)
              (progn
                ;; Read GUID and MODE from attributes
                (setq guid (_import_get_attr_value ent "GUID"))
                (setq mode (_import_get_attr_value ent "MODE"))
                (if (and guid (> (strlen guid) 0))
                  (progn
                    (setq blocks-with-guid (1+ blocks-with-guid))
                    ;; Merge attrs: panel base, circuits override, sections override (assoc uses first match)
                    (setq attrs-to-apply (append
                                          (or (_import_section_attrs dict-sections guid mode) '())
                                          (or (cdr (assoc guid dict-circuits)) '())
                                          (or (cdr (assoc guid dict-panel)) '())))
                    (if (and attrs-to-apply (> (length attrs-to-apply) 0))
                      (progn
                        (setq updated-count (+ updated-count
                                               (_import_apply_attrs ent attrs-to-apply)))
                        (entupd ent))
                      (setq guid-not-found (1+ guid-not-found))))
                  (setq skipped-no-guid (1+ skipped-no-guid))))
              (setq skipped-no-guid (1+ skipped-no-guid)))
            (setq i (1+ i)))
          ;; 5) Print summary
          (princ (strcat "\n--- IMPORT_ATTRS Summary ---"
                         "\n  blocks_scanned: " (itoa blocks-scanned)
                         "\n  blocks_with_guid: " (itoa blocks-with-guid)
                         "\n  updated_attrs_count: " (itoa updated-count)
                         "\n  blocks_skipped_no_guid: " (itoa skipped-no-guid)
                         "\n  guid_not_found_in_csv: " (itoa guid-not-found)
                         "\n----------------------------")))
        (princ "\nNo INSERT entities found in drawing.")))
  (princ))

;;; Parse CSV file: GUID,ATTR,VALUE (2-col value: ATTR,VALUE)
;;; Returns: ((GUID . ((ATTR . VALUE) ...)) ...)
(defun _import_parse_csv_2col (fpath / fd line parts guid attr val result row)
  (setq result '())
  (if (setq fd (open fpath "r"))
    (progn
      ;; Skip header
      (read-line fd)
      (while (setq line (read-line fd))
        (setq parts (_import_split_csv_line line))
        (if (>= (length parts) 3)
          (progn
            (setq guid (nth 0 parts)
                  attr (nth 1 parts)
                  val  (nth 2 parts))
            (setq row (assoc guid result))
            (if row
              (setq result (subst (cons guid (cons (cons attr val) (cdr row))) row result))
              (setq result (cons (cons guid (list (cons attr val))) result)))))
        )
      (close fd)
      (setq result (reverse result)))
    (princ (strcat "\nWarning: Could not open " fpath)))
  result)

;;; Parse CSV file: GUID,MODE,ATTR,VALUE (3-col value: MODE,ATTR,VALUE)
;;; Returns: ((GUID . ((MODE . ((ATTR . VALUE) ...)) ...)) ...)
(defun _import_parse_csv_3col (fpath / fd line parts guid mode attr val result row mode-row)
  (setq result '())
  (if (setq fd (open fpath "r"))
    (progn
      (read-line fd)
      (while (setq line (read-line fd))
        (setq parts (_import_split_csv_line line))
        (if (>= (length parts) 4)
          (progn
            (setq guid (nth 0 parts)
                  mode (nth 1 parts)
                  attr (nth 2 parts)
                  val  (nth 3 parts))
            (setq row (assoc guid result))
            (if row
              (progn
                (setq mode-row (assoc mode (cdr row)))
                (if mode-row
                  (setq result (subst (cons guid (subst (cons mode (cons (cons attr val) (cdr mode-row)))
                                                        mode-row
                                                        (cdr row)))
                                      row result))
                  (setq result (subst (cons guid (cons (cons mode (list (cons attr val))) (cdr row)))
                                     row result))))
              (setq result (cons (cons guid (list (cons mode (list (cons attr val))))) result)))))
        )
      (close fd)
      (setq result (reverse result)))
    (princ (strcat "\nWarning: Could not open " fpath)))
  result)

;;; Simple CSV line split by comma. Limitation: values must not contain commas.
(defun _import_split_csv_line (str / pos lst)
  (setq lst '())
  (while (and str (> (strlen str) 0))
    (if (setq pos (vl-string-search "," str))
      (progn
        (setq lst (append lst (list (vl-string-trim " \"" (substr str 1 pos)))))
        (setq str (substr str (+ pos 2))))
      (progn
        (setq lst (append lst (list (vl-string-trim " \"" str))))
        (setq str nil))))
  lst)

;;; Get attribute value by tag from block reference (INSERT with attributes).
(defun _import_get_attr_value (insert-ename tag / ent edata found)
  (setq ent (entnext insert-ename)
        found nil)
  (while (and ent
              (= (cdr (assoc 0 (setq edata (entget ent)))) "ATTRIB"))
    (if (= (strcase (cdr (assoc 2 edata))) (strcase tag))
      (setq found (cdr (assoc 1 edata))
            ent nil)
      (setq ent (entnext ent))))
  found)

;;; Get section attrs for GUID+MODE from dict-sections
(defun _import_section_attrs (dict-sections guid mode / row)
  (setq row (assoc guid dict-sections))
  (if row
    (cdr (assoc mode (cdr row)))
    nil))

;;; Apply attrs ((ATTR . VALUE) ...) to block. Skip GUID. Only update existing attrs.
;;; Returns count of updated attributes.
(defun _import_apply_attrs (insert-ename attrs / ent edata tag val count)
  (setq count 0
        ent (entnext insert-ename))
  (while (and ent (= (cdr (assoc 0 (setq edata (entget ent)))) "ATTRIB"))
    (setq tag (cdr (assoc 2 edata)))
    ;; Never update GUID
    (if (/= (strcase tag) "GUID")
      (progn
        (setq val (_import_attr_lookup attrs tag))
        (if val
          (progn
            (entmod (subst (cons 1 val) (assoc 1 edata) edata))
            (setq count (1+ count))))))
    (setq ent (entnext ent)))
  count)

;;; Helper: upcase keys in attrs alist for case-insensitive match
(defun _import_attrs_upcase (attrs / out)
  (setq out '())
  (foreach p attrs
    (if (listp p)
      (setq out (cons (cons (strcase (car p)) (cdr p)) out))))
  out)

(defun _import_attrs_downcase (attrs / out)
  (setq out '())
  (foreach p attrs
    (if (listp p)
      (setq out (cons (cons (strcase (car p) T) (cdr p)) out))))
  out)

;;; Fix assoc to be case-insensitive: search by tag in attrs
(defun _import_attr_lookup (attrs tag / p)
  (setq p (assoc tag attrs))
  (if p (cdr p)
    (progn
      (setq p (assoc (strcase tag) (_import_attrs_upcase attrs)))
      (if p (cdr p)
        (progn
          (setq p (assoc (strcase tag T) (_import_attrs_downcase attrs)))
          (if p (cdr p) nil))))))
