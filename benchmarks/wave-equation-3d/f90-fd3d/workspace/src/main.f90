program fd3d_cli
   use wave3d_solver
   implicit none

   integer :: nx, ny, nz, n_steps
   real(8) :: dt, dx
   integer :: argc, ix, iy, iz
   character(len=128) :: arg
   real(8), allocatable :: u_out(:, :, :)

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

   allocate (u_out(nx, ny, nz))
   call simulate_wave_3d(dt, dx, nx, ny, nz, n_steps, u_out)

   do ix = 1, nx
      do iy = 1, ny
         do iz = 1, nz
            write (*, '(G0.17)') u_out(ix, iy, iz)
         end do
      end do
   end do

end program fd3d_cli
