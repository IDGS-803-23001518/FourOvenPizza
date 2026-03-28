DELIMITER $$

DROP PROCEDURE IF EXISTS sp_gestion_productos $$
CREATE PROCEDURE sp_gestion_productos(
    IN p_accion VARCHAR(10),
    IN p_idProducto INT,
    IN p_nombre VARCHAR(100),
    IN p_precio DECIMAL(10,2),
    IN p_tamano VARCHAR(50),
    IN p_stock DECIMAL(10,2),
    IN p_estatus TINYINT,
    IN p_ip VARCHAR(50),
    IN p_usuario INT,
    OUT p_resultado VARCHAR(255),
    OUT p_idGenerado INT
)
BEGIN
    DECLARE v_nombre_producto VARCHAR(100) DEFAULT '';

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        SET p_resultado = 'ERROR: Ocurrio un error en la operacion';
        SET p_idGenerado = 0;
    END;

    START TRANSACTION;

    IF p_accion = 'INSERT' THEN

        IF EXISTS (
            SELECT 1
            FROM productos
            WHERE LOWER(TRIM(REGEXP_REPLACE(nombre, '[[:space:]]+[0-9]+$', ''))) =
                  LOWER(TRIM(REGEXP_REPLACE(p_nombre, '[[:space:]]+[0-9]+$', '')))
              AND LOWER(TRIM(`tamaño`)) = LOWER(TRIM(p_tamano))
        ) THEN

            SET p_resultado = 'ERROR: El producto ya existe';
            SET p_idGenerado = 0;
            ROLLBACK;

        ELSEIF p_precio < 0 THEN

            SET p_resultado = 'ERROR: El precio no puede ser negativo';
            SET p_idGenerado = 0;
            ROLLBACK;

        ELSEIF p_stock < 0 THEN

            SET p_resultado = 'ERROR: El stock no puede ser negativo';
            SET p_idGenerado = 0;
            ROLLBACK;

        ELSE

            INSERT INTO productos (`nombre`, `precio`, `tamaño`, `stock`, `estatus`)
            VALUES (TRIM(p_nombre), p_precio, TRIM(p_tamano), p_stock, 1);

            SET p_idGenerado = LAST_INSERT_ID();
            SET p_resultado = 'SUCCESS: Producto registrado correctamente';

            INSERT INTO bitacora_eventos (usuarioId, modulo, accion, referencia, fecha, ip)
            VALUES (
                p_usuario,
                'Productos',
                'INSERT',
                CONCAT('ID:', p_idGenerado, ' | ', TRIM(p_nombre), ' | ', TRIM(p_tamano)),
                NOW(),
                p_ip
            );

            COMMIT;

        END IF;

    ELSEIF p_accion = 'UPDATE' THEN

        IF NOT EXISTS (
            SELECT 1
            FROM productos
            WHERE idProducto = p_idProducto
        ) THEN

            SET p_resultado = 'ERROR: El producto no existe';
            SET p_idGenerado = 0;
            ROLLBACK;

        ELSEIF EXISTS (
            SELECT 1
            FROM productos
            WHERE LOWER(TRIM(REGEXP_REPLACE(nombre, '[[:space:]]+[0-9]+$', ''))) =
                  LOWER(TRIM(REGEXP_REPLACE(p_nombre, '[[:space:]]+[0-9]+$', '')))
              AND LOWER(TRIM(`tamaño`)) = LOWER(TRIM(p_tamano))
              AND idProducto <> p_idProducto
        ) THEN

            SET p_resultado = 'ERROR: Ya existe otro producto con el mismo nombre y tamaño';
            SET p_idGenerado = 0;
            ROLLBACK;

        ELSEIF p_precio < 0 THEN

            SET p_resultado = 'ERROR: El precio no puede ser negativo';
            SET p_idGenerado = 0;
            ROLLBACK;

        ELSEIF p_stock < 0 THEN

            SET p_resultado = 'ERROR: El stock no puede ser negativo';
            SET p_idGenerado = 0;
            ROLLBACK;

        ELSE

            UPDATE productos
            SET
                nombre = TRIM(p_nombre),
                precio = p_precio,
                `tamaño` = TRIM(p_tamano),
                stock = p_stock,
                estatus = p_estatus
            WHERE idProducto = p_idProducto;

            SET p_resultado = 'SUCCESS: Producto actualizado correctamente';
            SET p_idGenerado = p_idProducto;

            INSERT INTO bitacora_eventos (usuarioId, modulo, accion, referencia, fecha, ip)
            VALUES (
                p_usuario,
                'Productos',
                'UPDATE',
                CONCAT('ID:', p_idProducto, ' | ', TRIM(p_nombre), ' | ', TRIM(p_tamano)),
                NOW(),
                p_ip
            );

            COMMIT;

        END IF;

    ELSEIF p_accion = 'DELETE' THEN

        IF NOT EXISTS (
            SELECT 1
            FROM productos
            WHERE idProducto = p_idProducto
        ) THEN

            SET p_resultado = 'ERROR: El producto no existe';
            SET p_idGenerado = 0;
            ROLLBACK;

        ELSE

            SELECT nombre
              INTO v_nombre_producto
            FROM productos
            WHERE idProducto = p_idProducto;

            UPDATE productos
            SET estatus = 0
            WHERE idProducto = p_idProducto;

            SET p_resultado = 'SUCCESS: Producto desactivado correctamente';
            SET p_idGenerado = p_idProducto;

            INSERT INTO bitacora_eventos (usuarioId, modulo, accion, referencia, fecha, ip)
            VALUES (
                p_usuario,
                'Productos',
                'DELETE',
                CONCAT('ID:', p_idProducto, ' | ', v_nombre_producto),
                NOW(),
                p_ip
            );

            COMMIT;

        END IF;

    ELSE

        SET p_resultado = 'ERROR: Accion no valida';
        SET p_idGenerado = 0;
        ROLLBACK;

    END IF;

END $$

DELIMITER ;
