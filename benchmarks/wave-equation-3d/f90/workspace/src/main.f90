program fd3d_cli
   use wave3d_solver
   implicit none

   integer :: nx, ny, nz, n_steps, step
   real(8) :: dt, dx, sigma, x, y, z, r2
   integer :: argc, ix, iy, iz
   character(len=128) :: arg
   real(8), allocatable :: u(:, :, :), v(:, :, :)

   argc = command_argument_count()
   if (argc /= 6) then
      write (*, '(A)') 'usage: fd3d_cli <dt> <dx> <nx> <ny> <nz> <n_steps>'
      stop 2
   end if

   call get_command_argument(1, arg)
   read (arg, *) dt
   call get_command_argument(2, arg)
   read (arg, *) dx
   call get_command_argument(3, arg)
   read (arg, *) nx
   call get_command_argument(4, arg)
   read (arg, *) ny
   call get_command_argument(5, arg)
   read (arg, *) nz
   call get_command_argument(6, arg)
   read (arg, *) n_steps

   if (n_steps < 0 .or. nx <= 0 .or. ny <= 0 .or. nz <= 0 .or. dx <= 0.0d0 .or. dt < 0.0d0) then
      write (*, '(A)') 'invalid arguments'
      stop 1
   end if

   allocate (u(nx + 2, ny + 2, nz + 2))
   allocate (v(nx + 2, ny + 2, nz + 2))
   u = 0.0d0
   v = 0.0d0

   sigma = 0.1d0
   do iz = 2, nz + 1
      z = (real(iz - 2, kind=8) + 0.5d0)/real(nz, kind=8)
      do iy = 2, ny + 1
         y = (real(iy - 2, kind=8) + 0.5d0)/real(ny, kind=8)
         do ix = 2, nx + 1
            x = (real(ix - 2, kind=8) + 0.5d0)/real(nx, kind=8)
            r2 = (x - 0.5d0)**2 + (y - 0.5d0)**2 + (z - 0.5d0)**2
            u(ix, iy, iz) = exp(-r2/(2.0d0*sigma*sigma))
         end do
      end do
   end do
   call apply_periodic_ghosts(u, nx, ny, nz)
   call apply_periodic_ghosts(v, nx, ny, nz)

   do step = 1, n_steps
      call push_wave_3d(u, v, dt, dx, nx, ny, nz)
   end do

   do iz = 1, nz
      do iy = 1, ny
         do ix = 1, nx
            write (*, '(G0.17)') u(ix + 1, iy + 1, iz + 1)
         end do
      end do
   end do

end program fd3d_cli
