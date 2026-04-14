-- MySQL dump 10.13  Distrib 8.0.45, for Win64 (x86_64)
--
-- Host: 127.0.0.1    Database: fourovenpizzadb
-- ------------------------------------------------------
-- Server version	8.0.45

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Dumping data for table `ventas`
--

LOCK TABLES `ventas` WRITE;
/*!40000 ALTER TABLE `ventas` DISABLE KEYS */;
INSERT INTO `ventas` VALUES (1,1,'Ytang Magaña','2026-04-06 01:10:16','Punto venta','Efectivo','Confirmada'),(2,1,'Yaneth','2026-04-06 17:27:38','Punto venta','Efectivo','Confirmada'),(3,1,'Ytang','2026-04-08 17:35:12','Punto venta','Efectivo','Confirmada'),(4,1,'Ytang','2026-04-08 17:48:53','Punto venta','Efectivo','Confirmada'),(5,3,'Ytang Magaña | Dir: colonia, calle, 123, 37536','2026-04-09 17:20:18','En línea','Efectivo','Cancelada'),(6,3,'Ytang | Dir: Colonia, Calle, 123, 37500','2026-04-09 19:02:18','En línea','Efectivo','Lista para entregar'),(7,1,'Ytang','2026-04-10 01:02:19','Punto venta','Efectivo','En proceso'),(9,3,'Ytang Magaña | Dir: Colonia, Calle, 231, 37000','2026-04-12 15:05:11','En línea','Efectivo','Cancelada'),(10,3,'Ytang Magaña | Dir: Colonia, Calle, 123, 37000','2026-04-12 15:07:41','En línea','Efectivo','Confirmada'),(11,3,'Ytang Magaña | Dir: Colonia, Calle, 123, 37000','2026-04-13 02:36:55','En línea','Efectivo','Confirmada'),(12,1,'Roberto Martinez','2026-04-13 02:39:02','Punto venta','Efectivo','Confirmada'),(13,1,'Juan Martinez','2026-04-13 02:45:17','Punto venta','Tarjeta','Confirmada'),(14,1,'Raul Perez','2026-04-13 02:55:40','Punto venta','Efectivo','Confirmada'),(15,1,'Consumidor final','2026-04-13 03:06:51','Punto venta','Efectivo','Confirmada'),(16,3,'Juan Perez | Dir: Colonia, Calle, 123, 37000','2026-04-13 03:28:27','En línea','Efectivo','Cancelada'),(17,1,'Juan','2026-04-13 03:31:15','Punto venta','Efectivo','Cancelada'),(18,1,'Juan','2026-04-13 04:20:41','Punto venta','Efectivo','Cancelada'),(19,3,'Juan | Dir: Colonia, Calle, 123, 37000','2026-04-13 04:21:38','En línea','Efectivo','Cancelada'),(22,3,'Juan | Dir: Colonia, Calle, 123, 37000','2026-04-13 04:57:43','En línea','Efectivo','Confirmada'),(23,1,'Juan','2026-04-13 12:22:03','Punto venta','Efectivo','Cancelada');
/*!40000 ALTER TABLE `ventas` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-04-14  1:34:01
