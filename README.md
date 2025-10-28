<div align="center">

# **Python Distributed <br>Database**

</div>

### **Description**:

This project contains 3 apps used to create a simulation of a **distributed database**. It's goal is to present the Paxos and Raft consensus algorithms and compare them under different scenarios.

### **What is a distributed replicated database**
A distributed replicated database is a database that keeps copies of the same data on multiple computers in different places.

- The data is stored on many nodes
- Each node has a full or partial replica of the data
- When data changes, those updates are shared so all copies match
- If one node goes down, others still have the data so the system keeps working

It improves reliability and access speed, because the data is always
nearby and backed up in multiple locations.

## **Project Structure**

The project is made out of 3 different apps, each handeling a part of the simulation. Those apps can be found inside directories with corresponding names.


#### **The apps:**
*  [`server_app`](#server_app) - the app running on 3 servers, simulating the nodes of a distributed database
* [`sever_manager`](#server_manager) - the app responsible for managing all servers from one place to control shutting off separate servers and for viewing logs of all servers
* [`client_app`](#client_app) - a simple client-side app to give the visual representation of inputing and sending data

*The apps are described in separate sections.*

## **Setting up the project**

## **Project Apps**
### **server_app**
### **server_manager**
### **client_app**
