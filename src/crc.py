import time
import numpy as np
import csv
import struct

def toBytesList(num):
        """
        Split an int into a list of bytes
        :param num the int to convert
        """
        string = hex(num)[2:]
        if string[-1].lower() == 'l':
            string = string[:-1]

        #Watch out for leading zeros
        if len(string) % 2 != 0:
            string = '0' + string

        #Split into list and return
        return [int(string[i:i+2],16) for i in range(0,len(string),2)]

def crc4(p, polynomial=0x3, table=[]):
    """
    Calculates the CRC-4 checksum of a number by bitwise operations or by
    using a lookup table
    :param p is the list of bytes to find the CRC of (list of ints)
    :param polynomial the divisor polynomial to use
        Default is 0x3
    :param table provide the lookup table to calculate CRC that way
    	Is faster with table but can also be done without
    	Leave unset to calculate using bitwise operations instead
    :return the CRC4 checksum as an int
    """
    if type(p) == int or type(p) == long:
        p = toBytesList(p)

    #Initialize CRC to 0    
    crc = 0
    length = len(p)

    if table == []:
        for j in range(length):
	    crc ^= p[j]
	    for i in range(8): #Iterate through each bit
	        if crc & 0x80 != 0: #If MSD is 1
	            crc = ((crc << 1) & 0xFF) ^ (polynomial << 4)
	        else: #Shift the CRC so the MSD is 1
	            crc <<= 1
	            crc &= 0xFF #Don't keep anything beyond 8 bits
        return crc >> 4
    else: 
	for i in range(length):
	    #XOR-in next input byte into MSB of crc and get this MSB, that's our new intermediate divident
	    pos = (crc << 4 ^ (p[i])) & 0xFF
            #Update the CRC from the Lookup table
            crc = int(table[pos])
        return crc

def calculate_CRC4_table():
    """
    Generates a lookup table to find the CRC-4 checksum of a number
    :return the table as a list of 256 values
    """
    polynomial = 0x3;
    row = []
    CRC4_table = np.zeros(256)
    with open('CRC4_LUT.csv','w') as csvfile:
        outfile = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        i = 0
        for dividend in range(256): # iterate over all possible input byte values 0 - 255
            curByte = dividend & 0xFF;
            for bit in range(8):
                if (curByte & 0x80) != 0:
                    curByte <<= 1
                    curByte ^=  (polynomial << 4)
                    curByte &= 0xFF
                else:
                    curByte <<= 1
                    curByte &= 0xFF
            curByte >>= 4
            
            row.append(hex(curByte))
            if ((dividend+1)%16 == 0):
                outfile.writerow(row)
                row = []
                
            CRC4_table[i] = curByte
            i += 1
            
            
        return CRC4_table

def crc32(p, polynomial=0x04C11DB7, table=[]):
    """
    Calculates the CRC-32 checksum of a number using bitwise operations
    or with a lookup table
    :param p is the list of bytes to find the CRC of (list of ints)
    :param polynomial the divisor polynomial to use
        Default is 0x04C11DB7
    :param table provide the lookup table to calculate CRC that way
    	Is faster with table but can also be done without
    	Leave unset to calculate using bitwise operations instead
    :return the CRC32 checksum as an int
    """

    if type(p) == int or type(p) == long:
        p = toBytesList(p)

    length = len(p)
    crc = 0 #CRC value is 32bit

    if table == []:
        for j in range(length):
	    crc ^= (p[j] << 24) # move byte into MSB of 32bit CRC
	    crc &= 0xFFFFFFFF #Keep crc 32 bits
	        
	    for i in range(8):
	        if (crc & 0x80000000) != 0: #test for MSB = bit 31
	            crc = ((crc << 1) ^ polynomial) & 0xFFFFFFFF
	        else:
	            crc <<= 1;
	            crc &= 0xFFFFFFFF #Keep crc 32 bits
    else: 
        for i in range(length):
	    #XOR-in next input byte into MSB of crc and get this MSB, that's our new intermediate dividend
	    pos = ((crc ^ (p[i] << 24)) >> 24) & 0xFF
	    #Shift out the MSB used for division per lookup table and XOR with the remainder
	    crc = ((crc << 8) ^ int(table[pos])) & 0xFFFFFFFF

    return crc


def calculate_CRC32_table():
    """
    Generates a lookup table to find the CRC-32 checksum of a number
    :return the table as a list of 256 ints
    """
    polynomial = 0x04C11DB7;
    row = []
    CRC32_table = np.zeros(256)
    with open('CRC32_LUT.csv','w') as csvfile:
        outfile = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        i = 0
        for dividend in range(256): # iterate over all possible input byte values 0 - 255
            curByte = dividend << 24;
            for bit in range(8):
                if (curByte & 0x80000000) != 0:
                    curByte <<= 1
                    curByte ^=  polynomial
                    curByte &= 0xFFFFFFFF
                else:
                    curByte <<= 1
                    curByte &= 0xFFFFFFFF
            
            row.append(hex(curByte))
            if ((dividend+1)%8 == 0):
                outfile.writerow(row)
                row = []
                
            CRC32_table[i] = curByte
            i += 1
            
            
        return CRC32_table.astype('int')

def crc8(p,polynomial=0x07,table=[]):
	"""
	Calculates the CRC-8 checksum of a number by bitwise operations or by
	using a lookup table
	:param p is the list of bytes to find the CRC of (list of ints)
	:param polynomial the divisor polynomial to use
	Default is 0x
	:param table provide the lookup table to calculate CRC that way
	Is faster with table but can also be done without
	Leave unset to calculate using bitwise operations instead
	:return the CRC-8 checksum as an int
	"""
    	if type(p) == int or type(p) == long:
        	p = toBytesList(p)

	#Initialize CRC to 0    
	crc = 0
	length = len(p)

	if table == []:
		for j in range(length):
			crc ^= p[j] #move byte into MSB of 8bit CRC
            		crc &= 0xFF

			for i in range(8):
				if (crc & 0x80) != 0: # test for MSB = bit 7
					crc = ((crc << 1) ^ polynomial) & 0xFF
				else:
					crc <<= 1
					crc &= 0xFF #Discard anything beyond 8 bits
	else:
		for i in range(length):
			#XOR-in next input byte into MSB of crc and get this MSB, that's our new intermediate divident
			pos = (crc ^ (p[i])) & 0xFF
			#Update the CRC from the lookup table
			crc = int(table[pos])
	return crc & 0xFF

def calculate_CRC8_table():
    """
    Generates a lookup table to find the CRC-8 checksum of a number
    :return the table as a list of 256 ints
    """
    polynomial = 0x07
    row = []
    CRC8_table = np.zeros(256)
    with open('CRC8_LUT.csv','w') as csvfile:
        outfile = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        i = 0

        for dividend in range(256):# iterate over all possible input byte values 0 - 255 */
            curByte = dividend;
            for bit in range(8):
                if (curByte & 0x80) != 0:
                    curByte <<= 1
                    curByte ^= polynomial
                    curByte &= 0xFF
                else:
                    curByte <<= 1
                    curByte &= 0xFF

            row.append(hex(curByte))
            if ((dividend+1)%16 == 0):
                outfile.writerow(row)
                row = []

            CRC8_table[dividend] = curByte;
    return CRC8_table.astype('int')
