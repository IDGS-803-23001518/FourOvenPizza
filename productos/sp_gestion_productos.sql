DELIMITER $$

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

    START TRANSACTION;

    IF p_accion = 'INSERT' THEN

        IF EXISTS (SELECT 1 FROM productos WHERE nombre = p_nombre AND `tamaño` = p_tamano) THEN

            SET p_resultado = 'ERROR: El producto ya existe';
            SET p_idGenerado = 0;
            ROLLBACK;

        ELSE

            INSERT INTO productos (`nombre`, `precio`, `tamaño`, `stock`, `estatus`)
            VALUES (p_nombre, p_precio, p_tamano, p_stock, 1);

            SET p_idGenerado = LAST_INSERT_ID();
            SET p_resultado = 'SUCCESS: Producto registrado correctamente';

            INSERT INTO bitacora_eventos (usuarioId, modulo, accion, referencia, fecha, ip)
            VALUES (p_usuario, 'Productos', 'INSERT', p_nombre, NOW(), p_ip);

            COMMIT;

        END IF;

    ELSEIF p_accion = 'UPDATE' THEN

        IF NOT EXISTS (SELECT 1 FROM productos WHERE idProducto = p_idProducto) THEN

            SET p_resultado = 'ERROR: El producto no existe';
            SET p_idGenerado = 0;
            ROLLBACK;

        ELSE

            UPDATE productos
            SET
                nombre = p_nombre,
                precio = p_precio,
                `tamaño` = p_tamano,
                stock = p_stock,
                estatus = p_estatus
            WHERE idProducto = p_idProducto;

            SET p_resultado = 'SUCCESS: Producto actualizado correctamente';
            SET p_idGenerado = p_idProducto;

            INSERT INTO bitacora_eventos (usuarioId, modulo, accion, referencia, fecha, ip)
            VALUES (p_usuario, 'Productos', 'UPDATE', p_nombre, NOW(), p_ip);

            COMMIT;

        END IF;

    ELSEIF p_accion = 'DELETE' THEN

        IF NOT EXISTS (SELECT 1 FROM productos WHERE idProducto = p_idProducto) THEN

            SET p_resultado = 'ERROR: El producto no existe';
            SET p_idGenerado = 0;
            ROLLBACK;

        ELSE

            UPDATE productos
            SET estatus = 0
            WHERE idProducto = p_idProducto;

            SET p_resultado = 'SUCCESS: Producto desactivado correctamente';
            SET p_idGenerado = p_idProducto;

            INSERT INTO bitacora_eventos (usuarioId, modulo, accion, referencia, fecha, ip)
            VALUES (p_usuario, 'Productos', 'DELETE', p_idProducto, NOW(), p_ip);

            COMMIT;

        END IF;

    END IF;

END $$

DELIMITER ;
