#! /usr/bin/env python

import rospy
import ftd2xx
from forcesensor.msg import SensorOutput
from forcesensor.msg import UserCommand
from forcesensor.msg import ByteMsg
from forcesensor.msg import FlagMsg
from std_msgs.msg import Int32
from std_msgs.msg import Bool

class Serial_Device:

	def __init__(self, port_num=0, sensor_num=0):

		self.INIT_BYTE = 0xAA
		self.port_num = port_num
		self.baud = 5000000
		self.conti_read_flag = False
		self.sensor_num = sensor_num
		self.report_ids = {
			0x01: 'Accelerometer',
			0x02: 'Gyroscope',
			0x04: 'Linear Acceleration',
			0x05: 'Rotation Vector',
			0x08: 'Game Rotation Vector'
			}

		###Set up ROS
		rospy.init_node('port' + str(self.sensor_num))
		self.rate = rospy.Rate(1500)

		#queue_size limits the number of queued messages if a subscriber is reading too slowly
		#Create publisher to write continuous data to topic using custom message type
		self.continuous_data_pub = rospy.Publisher('continuous_data', SensorOutput, queue_size=10)
		#Create publishers to write single responses to topics for sensor object to read
		self.byte_response_pub = rospy.Publisher('byte_response', ByteMsg, queue_size=1)
		self.packet_response_pub = rospy.Publisher('packet_response', SensorOutput, queue_size=1)
		#Listen to user commands and interrupt action to carry out the command
		self.user_cmds = rospy.Subscriber('user_commands', UserCommand, self.send_byte)
		#Listen to user commands to dstart or stop continuous data transfer
		self.run_flag = rospy.Subscriber('continuous_data_flag' + str(self.sensor_num), FlagMsg, self.changeFlag)

		###Initialize serial port
		#Connect sensor serial port given by portNum (Usually 0,1, or 2)
		# self.port = ftd2xx.open(port_num)
		try:
			self.port = ftd2xx.open(0)
			rospy.logwarn('Opened port 0')
		except ftd2xx.ftd2xx.DeviceError:
			self.port = ftd2xx.open(1)
			rospy.logwarn('Opened port 1')

		#Set latency timer to 1ms (lowest possible value. Ideally would be lower but limited by USB frame size)
		self.port.setLatencyTimer(1)
		#Set read an write timeouts 
		self.port.setTimeouts(16,16)
		#Set USB package size to smallest possible value to avoid waiting for package until timeout for package to fill
		self.port.setUSBParameters(64)
		#Set baud rate to rate specified above
		self.port.setBaudRate(self.baud)
		self.reset() #reset transmit and receive buffers

		##Run loop - do this forever in the background
		while not rospy.is_shutdown():
			while self.conti_read_flag:
				#Wait for initialization bit and matching CRC-4
				if self.wait_for_packet(port):
					data = self.port.read(51)
					#Check CRC-32 of data packet
					if self.check_crc(self.to_int(data[47:]), data[:47]):
						#Parse and publish if correct, otherwise ignore
						parsed = self.parse(data)
						self.continuous_data_pub.publish(parsed)
				self.rate.sleep()
			self.rate.sleep()

		self.port.write(b'\x11')
		self.port.purge()
		self.port.close()

	def __del__(self):
		self.port.close()


	def send_byte(self, msg):
		"""
		Callback function for the user command topic. This is called whenever the user issues a command
		other than start/stop continuous data transfer. The message contains two ints. First, the command byte
		that is sent to the sensor, and second, the length of the expected response of the sensor. This function
		attempts to read in this many bytes and publishes them to the byte_response topic. For the case of the byte
		command being 0x12, we expect a data packet to be sent, so it will be checked for CRC correctness, parsed,
		and written to the packet_response topic 	
		"""

		self.port.write(bytes([msg.command_byte]))
		self.port.purge(1)
		length = int(msg.expected_response_length)
		cmd_byte = int(msg.command_byte)
		rospy.logwarn('Expected length: ' + str(length))
		rospy.logwarn('Received command: ' + str(cmd_byte))
		#If we expect a response, read in the expected length
		if length > 0:
			#Special case where we read one packet
			if int(cmd_byte) == 12:
				count = 0
				while count < 100:
					#Wait for init byte or timeout
					if self.wait_for_packet(self.port):
						data = self.port.read(51)
						#Check CRC-32 of data packet
						if self.check_crc(self.to_int(data[47:]), data[:47]):
							#Parse and publish if correct
							parsed = self.parse(data)
							self.packet_response_pub.publish(parsed)
							break
						else:
							#If CRC was wrong, try again
							self.port.write(bytes([msg]))
							self.port.purge(1)
					else: #If timed out before start byte found try again
						self.port.write(bytes([msg]))
						self.port.purge(1)
					count += 1
				if count == 100:
					self.byte_response_pub.publish(-1)
			else:
				#Usually just read response byte
				count = 0
				while count < 100:
					if self.port.getQueueStatus() == length:
						data = self.port.read(length)
						rospy.logwarn(data)
						self.byte_response_pub.publish(int(data.hex(),16))
					count += 1
				if count == 100:
					self.byte_response_pub.publish(-1)

	def reset(self):
			"""
			Reset all input and output buffers until there are no more bytes waiting.
			If the buffer keeps filling up with new data after the reset, this will try
			100 times to clear the buffers before it gives up because something is continuosly
			writing to the buffer
			"""
			i = 0
			while self.port.getQueueStatus() > 0 and i < 100:
				self.port.resetDevice()
				i += 1

			if i == 100:
				print('Failed to reset. Ensure nothing is actively sending data')

	def check_crc(self, crc, p, n=32, polynomial=0xedb88320):
		    """
		    Check CRC Checksum with arbitrary number of bits
		    :param crc the n bit checksum in hex or int - note that the sensor returns LSB first, 
		        so can't just use sensor output here
		    :param p the packet to compare to the checksum. (This is bytes 0 to 46 in the 51 byte sensor packet)
		    :param polynomial the bit string of the CRC polynomial to use
		    :return True if the checksum matches, False otherwise
		    """
		    
		    #Convert p to correct type
		    if type(p) == bytes:
		   		p = int(p.hex(),16)

		    #Construct the number: <4 bit counter><init byte><4 bit crc>
		    p = (p << n) + crc #Append the crc to the end of the number
		    pBin = bin(p)[2:] #Store the binary representation of the number
		    length = len(pBin)
		    poly = polynomial << length - len(bin(polynomial))+2 #Shift the polynomial to align with most significant bit
		    minVal = 2**n #When p gets smaller than this, the dividend is zero
		    i = 0 #Start aligned with most significant bit

		    while p >= minVal: #Terminate when the dividend is equal to zero and only the checksum portion remains
		        while pBin[i] == '0' and i <= length-n: #Shift the divisor until it is aligned with the most significant 1
		            i = i + 1
		            poly = poly >> 1
		        p = p ^ poly #XOR the number with the divisor
		        pBin = bin(p)[2:] #Update the bit string for checking
		        #Make sure leading zeros weren't removed by Python
		        while len(pBin) < length:
		            pBin = '0' + pBin
		    return p == 0

	def wait_for_packet(self, timeout=100):
		for i in range(timeout):
			#Check for initialization byte
			if self.port.read(1) == bytes([self.INIT_BYTE]):
				#Read next byte
				byte = self.port.read(1)

				#Store 4 LSBs of the byte (the checksum)
				crc = byte[0] & 0x0F

				#Combine initialization byte and counter by shifting 4 bits and adding
				p = (INIT_BYTE << 4) + ((byte[0] & 0xF0) >> 4) #4 MSBs of byte are the counter

				#Test checksum
				return self.check_crc(crc,p,4,0x9)
		return False

	def parse(self, byte_data):
		"""
		Parse the data packet of 51 bytes using the SH-2 structure
		:param byte_data 51-byte-long bytes object
		:return sensor_output object which contains the parsed data in a useful form
		"""

		#Create sensor output object
		data_out = SensorOutput()

		#Convert all 6 values in differentials and sums to ints
		data_out.differential = [to_int(byte_data[i:i+3]) for i in {0, 3, 6, 9, 12, 15}]
		data_out.sum = [to_int(byte_data[i:i+3]) for i in {18, 21, 24, 27, 30, 33}]
		
		data_out.report_id = REPORT_IDS[byte_data[37]]
		data_out.sequence_num = byte_data[38]
		status = '{0:08b}'.format(byte_data[39])
		data_out.accuracy = int(status[-2:],2) #0=Unreliable, 1=Low, 2=Medium, 3=High
		data_out.delay = (byte_data[40] + int(status[0:-2] + '0000000',2)) * 100e-6 #delay in seconds

		#LSB is first byte that is returned
		x = to_int(byte_data[41:43])
		y = to_int(byte_data[43:45])
		z = to_int(byte_data[45:47])
		data_out.imu = {x,y,z}

		#Again, LSB comes first
		data_out.checksum = to_int(byte_data[47:])

		#Note which sensor this came from
		data_out.sensor_num = self.sensor_num

		return data_out

	def to_int(self, byte):
		"""
		Helper method to convert a bytes object where the least significant byte is first into an int
		"""
		num = 0
		for i in range(len(byte)):
			num += (byte[i] << i*8)
		return num

	def changeFlag(self, msg):
		"""
		Change the flag to notify the main loop about whether it should measure
		Also send the command byte to the sensor that tells it to start or stop
		transmission of continuous data
		"""
		self.conti_read_flag = msg

		if msg == True:
			#Prompt the start of continuous data transmission
			self.port.write(b'\x10')
			self.port.purge()
		else:
			#Prompt the end of continuous data transmission
			self.port.write(b'\x11')
			self.port.purge()

if __name__ == "__main__":
	if rospy.has_param('has_sensor'):
		port1 = Serial_Device(1,1)
	else:
		rospy.set_param('has_sensor', True)
		port0 = Serial_Device()
		




